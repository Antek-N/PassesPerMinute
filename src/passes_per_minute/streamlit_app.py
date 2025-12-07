import json
import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import streamlit as st

from passes_per_minute.passes_counter import (
    get_competition_seasons,
    process_competition,
)
from passes_per_minute.passes_counter.player_position_stats import calculate_average_passes
from passes_per_minute.plotter import plot_bar_chart, plot_pitch_chart

# Configure logging to console
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Suppress Matplotlib GUI windows
plt.show = lambda: None  # type: ignore[assignment, misc]

# Configuration constants
DATA_FILE_PATH = os.path.join(os.path.dirname(__file__), "data", "granular_stats.json")
DEFAULT_COMPETITION_IDS = [9, 1267, 16, 223, 87, 43, 11, 81, 7, 2, 12, 55, 35]
DEFAULT_START_YEAR = 2009
DEFAULT_END_YEAR = 2024


# ==============================================================================
# UI & Visualization Helpers
# ==============================================================================


def prepare_table_data(processed_data: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    """
    Format raw statistics into a list of dictionaries suitable for a Streamlit dataframe.

    :param processed_data: Dictionary {position: {'passes': int, 'minutes': int}}
    :return: List of row dictionaries ready for display

    Example
    -------
    > processed = {
    ...     "CM": {"passes": 100, "minutes": 200},
    ...     "ST": {"passes": 50, "minutes": 100},
    ...     "GK": {"passes": 10, "minutes": 200}
    ... }

    > prepare_table_data(processed)
    [
        {'Position': 'CM', 'Passes (Total)': 100, 'Minutes (Total)': 200, 'Avg Passes/Min': 0.5},
        {'Position': 'ST', 'Passes (Total)': 50, 'Minutes (Total)': 100, 'Avg Passes/Min': 0.5},
        {'Position': 'GK', 'Passes (Total)': 10, 'Minutes (Total)': 200, 'Avg Passes/Min': 0.05},
    ]
    """
    table_data_list = []

    # Iterate through positions and calculate metrics
    for position_name, statistics in processed_data.items():
        # Count average
        average_passes = (
            statistics["passes"] / statistics["minutes"] if statistics["minutes"] > 0 else 0  # Avoid division by zero
        )

        # Add data to list
        table_data_list.append(
            {
                "Position": position_name,
                "Passes (Total)": statistics["passes"],
                "Minutes (Total)": statistics["minutes"],
                "Avg Passes/Min": average_passes,
            }
        )

    # Sort results by efficiency (Avg Passes/Min) in descending order
    table_data_list.sort(key=lambda row: float(row["Avg Passes/Min"]), reverse=True)  # type: ignore[arg-type]

    return table_data_list


def render_dashboard(plot_data: dict[str, float], raw_stats: dict[str, dict[str, int]]) -> None:
    """
    Render the main visual components: Bar Chart, Pitch Map, and Data Table.
    """
    st.markdown("---")

    # Create tabs for different views
    bar_chart_tab, pitch_map_tab, data_table_tab = st.tabs(["Bar Chart", "Pitch Map", "Data Table"])

    # --- Tab 1: Bar Chart ---
    with bar_chart_tab:
        try:
            bar_figure, _, _ = plot_bar_chart(plot_data, "Average Passes per Minute")

            # Center plot
            left_col, center_col, right_col = st.columns([1, 2, 1])
            with center_col:
                st.pyplot(bar_figure)

        except Exception as error:
            st.error(f"Error generating bar chart: {error}")

    # --- Tab 2: Pitch Map ---
    with pitch_map_tab:
        try:
            pitch_figure, _ = plot_pitch_chart(plot_data, "Average Passes per Minute")

            # Center plot
            left_col, center_col, right_col = st.columns([1, 2, 1])
            with center_col:
                st.pyplot(pitch_figure)

        except Exception as error:
            st.error(f"Error generating pitch map: {error}")

    # --- Tab 3: Detailed Data Table ---
    with data_table_tab:
        detailed_table_data = prepare_table_data(raw_stats)

        st.dataframe(
            detailed_table_data,
            column_config={"Avg Passes/Min": st.column_config.NumberColumn(format="%.4f")},
            use_container_width=True,
            hide_index=True,
        )


def configure_page() -> None:
    """
    Set up the Streamlit page configuration, title, and layout.
    """
    base = Path(__file__).resolve().parent
    icon_path = base / "assets" / "img" / "icon.png"

    st.set_page_config(
        page_title="Passes Per Minute",
        page_icon=str(icon_path),
        layout="wide",
    )
    st.title("Passes Per Minute Analysis")


# ==============================================================================
# Fast Mode Logic (Offline / Pre-calculated)
# ==============================================================================


@st.cache_data(show_spinner=False)
def _load_local_database() -> list[dict[str, Any]] | None:
    """
    Load the pre-computed granular statistics from the local JSON file.

    :return: A list of season data entries (the 'bricks') or None if the file is missing
    """
    # Check if the offline database file exists
    if not os.path.exists(DATA_FILE_PATH):
        return None

    # Open and load data from file
    try:
        with open(DATA_FILE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load local database: {e}")
        return None


def _filter_and_aggregate_database(
    database: list[dict[str, Any]], start_year: int, end_year: int, selected_comp_ids: list[int]
) -> tuple[dict[str, dict[str, int]], int]:
    """
    Filter the granular database in memory and aggregate stats on the fly.

    :param database: List of all season entries
    :param start_year: Filter start year (inclusive)
    :param end_year: Filter end year (inclusive)
    :param selected_comp_ids: List of competition IDs to include
    :return: A tuple containing the aggregated stats dictionary and the count of processed seasons

    Example
    -------
    > db = [
    ...     {"meta": {"year": 2020, "competition_id": 9},
    ...      "stats": {"CM": {"passes": 100, "minutes": 200}}},
    ...     {"meta": {"year": 2021, "competition_id": 9},
    ...      "stats": {"CM": {"passes": 50, "minutes": 100},
    ...                "ST": {"passes": 30, "minutes": 80}}},
    ...     {"meta": {"year": 2019, "competition_id": 7},
    ...      "stats": {"CM": {"passes": 70, "minutes": 150}}}
    ... ]

    > _filter_and_aggregate_database(db, 2020, 2021, [9])
        ( {'CM': {'passes': 150, 'minutes': 300},
        'ST': {'passes': 30, 'minutes': 80}},
        2 )

    """
    aggregated_stats: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"passes": 0, "minutes": 0})
    processed_count = 0

    for entry in database:
        meta = entry["meta"]

        # Check if the entry matches the selected criteria
        if start_year <= meta["year"] <= end_year and meta["competition_id"] in selected_comp_ids:
            processed_count += 1
            season_stats = entry["stats"]

            # Aggregate stats for each position
            for position, values in season_stats.items():
                aggregated_stats[position]["passes"] += values["passes"]
                aggregated_stats[position]["minutes"] += values["minutes"]

    return aggregated_stats, processed_count


def run_fast_mode(database: list[dict[str, Any]]) -> None:
    """
    Execute the application in Fast Mode (using preloaded JSON data).

    :param database: The loaded list of granular season data
    """
    st.success("✅ Fast Mode Active: Using pre-computed offline data.")

    # --- Prepare Sidebar Data ---
    # Extract available competitions from metadata to populate the filter UI
    available_competitions = {}
    for entry in database:
        meta = entry["meta"]
        available_competitions[meta["competition_id"]] = meta["competition_name"]

    # Sort competitions alphabetically for better UX
    comp_options = sorted(available_competitions.items(), key=lambda item: item[1])

    # --- Sidebar UI Controls ---
    st.sidebar.header("Filter Data")

    selected_year_range = st.sidebar.slider(
        "Year Range", min_value=1990, max_value=2024, value=(DEFAULT_START_YEAR, DEFAULT_END_YEAR)
    )

    selected_comp_names = st.sidebar.multiselect(
        "Select Competitions", options=[name for _, name in comp_options], default=[name for _, name in comp_options]
    )

    # Map selected names back to IDs for filtering
    selected_ids = [comp_id for comp_id, name in comp_options if name in selected_comp_names]

    # --- Real-time Processing ---
    aggregated_stats, season_count = _filter_and_aggregate_database(
        database, selected_year_range[0], selected_year_range[1], selected_ids
    )

    # If no data
    if season_count == 0:
        st.warning("No data found for the selected filters.")
        return

    st.info(f"Analysis based on {season_count} seasons.")

    # --- Calculation and Rendering ---
    average_passes_list = calculate_average_passes(aggregated_stats)
    plot_data_dictionary = dict(average_passes_list)

    render_dashboard(plot_data_dictionary, aggregated_stats)


# ==============================================================================
# Live Mode Logic (Fallback / Online)
# ==============================================================================


def parse_competition_ids(id_string: str) -> list[int]:
    """
    Parse comma-separated ID string into a list of integers.

    :param id_string: The raw string input from the user
    :return: A list of integer IDs
    :raises ValueError: If parsing fails

     Example
    -------
    > parse_competition_ids("9, 16, 55")
    > [9, 16, 55]
    """
    try:
        return [int(x.strip()) for x in id_string.split(",") if x.strip()]
    except ValueError as e:
        raise ValueError("Invalid ID format. Please use numbers separated by commas.") from e


def _get_live_mode_config() -> tuple[tuple[int, int], str, bool]:
    """
    Renders the sidebar configuration widgets for the Live Mode.

    :return: A tuple containing the selected year range, the raw competition IDs string,
             and the boolean state of the run button.
    """
    st.sidebar.header("Live Configuration")

    # Slider for selecting the analysis period
    selected_year_range = st.sidebar.slider(
        "Year Range", min_value=1990, max_value=2024, value=(DEFAULT_START_YEAR, DEFAULT_END_YEAR)
    )

    # Text area for entering competition IDs
    ids_input_string = st.sidebar.text_area(
        "Competition IDs (comma separated)",
        value=", ".join(map(str, DEFAULT_COMPETITION_IDS)),
        help="Enter the competition IDs you want to analyze.",
    )

    is_run_clicked = st.sidebar.button("Run Live Analysis", type="primary")

    return selected_year_range, ids_input_string, is_run_clicked


def _process_competitions_multithreaded(valid_competitions: list[tuple[int, int]]) -> dict[str, dict[str, int]]:
    """
    Executes the data processing pipeline for a list of competitions using multithreading.

    This function handles the thread pool, updates the Streamlit UI progress bar,
    and aggregates the results from individual match processing tasks.

    :param valid_competitions: A list of tuples, where each tuple contains (competition_id, season_id).
    :return: A dictionary containing aggregated statistics keyed by player position.
             Example: {'Midfielder': {'passes': 150, 'minutes': 2000}, ...}
    """
    aggregated_stats: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"passes": 0, "minutes": 0})

    # Initialize UI progress components
    progress_bar = st.progress(0)
    status_text = st.empty()

    total_tasks = len(valid_competitions)
    completed_tasks = 0

    # Execute tasks in parallel to speed up data fetching
    with ThreadPoolExecutor() as executor:
        future_map = {executor.submit(process_competition, cid, sid): (cid, sid) for cid, sid in valid_competitions}

        for future in as_completed(future_map):
            try:
                result = future.result()

                # Accumulate results from the finished task into the main dictionary
                for position, stats in result.items():
                    aggregated_stats[position]["passes"] += stats["passes"]
                    aggregated_stats[position]["minutes"] += stats["minutes"]

            except Exception as e:
                # Log the error but allow other threads to continue
                log.error(f"Error processing season: {e}")

            # Update the progress bar and status text
            completed_tasks += 1
            progress_bar.progress(int((completed_tasks / total_tasks) * 100))
            status_text.text(f"Processing: {completed_tasks}/{total_tasks} seasons...")

    # Clean up UI components after processing is complete
    progress_bar.empty()
    status_text.empty()

    return aggregated_stats


def run_live_mode() -> None:
    """
    Orchestrates the Live Mode application flow (fetching data from StatsBomb API).

    This function acts as the main controller that connects UI configuration,
    input validation, data fetching, processing pipeline, and final rendering.
    Used as a fallback when local JSON data is missing.
    """
    st.info("ℹ️ Live Mode: Fetching data from internet (Local DB not found).")

    # --- Step 1: Sidebar Configuration ---
    selected_year_range, ids_input_string, is_run_clicked = _get_live_mode_config()

    if not is_run_clicked:
        st.write("Set parameters in the sidebar and click 'Run Live Analysis'.")
        return

    # --- Step 2: Input Validation ---
    try:
        target_ids = parse_competition_ids(ids_input_string)
    except ValueError as e:
        st.error(str(e))
        return

    # --- Step 3: Fetch Seasons Metadata ---
    with st.spinner("Fetching available seasons..."):
        valid_competitions = get_competition_seasons(selected_year_range[0], selected_year_range[1], target_ids)

    if not valid_competitions:
        st.warning("No competitions found for the given criteria.")
        return

    st.success(f"Found {len(valid_competitions)} matching seasons. Starting download...")

    # --- Step 4: Process Matches (Multithreaded) ---
    aggregated_stats = _process_competitions_multithreaded(valid_competitions)

    # --- Step 5: Render Results ---
    average_passes_list = calculate_average_passes(aggregated_stats)
    plot_data_dictionary = dict(average_passes_list)

    render_dashboard(plot_data_dictionary, aggregated_stats)


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> None:
    """
    Main entry point for the Streamlit application.

    This function initializes the page configuration and determines the execution mode:
    1. **Fast Mode**: Uses pre-computed local JSON data (if available and not overridden).
    2. **Live Mode**: Fetches data from the API (fallback or forced).
    """
    # --- Initialize App and Load Data ---
    configure_page()
    granular_database = _load_local_database()
    force_live_mode = False

    # --- Sidebar: Debug Options ---
    # Allow the user to force "Live Mode" even if local data exists
    if granular_database:
        st.sidebar.header("Debug / Settings")
        force_live_mode = st.sidebar.checkbox("Force Live Mode (Ignore local DB)", value=False)

    # --- Mode Selection & Execution ---
    # Case 1: Fast Mode (Local data exists and user hasn't forced live mode)
    if granular_database and not force_live_mode:
        run_fast_mode(granular_database)

    # Case 2: Live Mode (No local data OR user forced live mode)
    else:
        if force_live_mode:
            st.warning("⚠️ Running in Forced Live Mode (Local DB ignored)")
        run_live_mode()


if __name__ == "__main__":
    main()
