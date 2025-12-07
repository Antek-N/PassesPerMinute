import json
import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from passes_per_minute.passes_counter import (
    draw_plots,
    fetch_competitions,
    get_match_counter,
    print_summary,
    process_competition,
)

log = logging.getLogger(__name__)

TARGET_COMP_IDS = [9]
START_YEAR = 2009
END_YEAR = 2024
DB_FILENAME = "granular_stats.json"


def fetch_and_filter_seasons(start_year: int, end_year: int, target_ids: list[int]) -> list[dict[str, Any]]:
    """
    Fetch all available competitions and filter them by target IDs and year range.

    :param start_year: The inclusive start year for filtering
    :param end_year: The inclusive end year for filtering
    :param target_ids: List of competition IDs to include
    :return: A list of metadata dictionaries for the matching seasons
    """
    # Attempt to retrieve the raw list of competitions
    try:
        all_competitions = fetch_competitions()
    except (requests.exceptions.RequestException, RuntimeError) as e:
        log.error("Failed to fetch competition list: %s", e)
        return []

    tasks_metadata = []

    # Iterate through all competitions to find matches
    for comp in all_competitions:
        try:
            season_name = comp["season_name"]
            # Handle formats like "2018/2019" (take 2018) or "2018"
            year_str = season_name.split("/")[0] if "/" in season_name else season_name
            year = int(year_str)
        except ValueError:
            # Skip entries where the year cannot be parsed
            continue

        # Check if the competition matches our criteria
        if comp["competition_id"] in target_ids and start_year <= year <= end_year:
            tasks_metadata.append(
                {
                    "competition_id": comp["competition_id"],
                    "season_id": comp["season_id"],
                    "season_name": season_name,
                    "competition_name": comp["competition_name"],
                    "year": year,
                }
            )

    return tasks_metadata


def build_granular_database(tasks_metadata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Process specific seasons concurrently to build a granular stats' database.

    :param tasks_metadata: List of metadata dictionaries defining which seasons to process
    :return: A list of processed season entries containing metadata and stats
    """
    database = []
    total = len(tasks_metadata)
    count = 0

    log.info(f"Starting concurrent processing for {total} seasons...")

    # Use a thread pool to speed up network requests/processing
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Map the future object back to its metadata for logging purposes
        future_to_meta = {
            executor.submit(process_competition, t["competition_id"], t["season_id"]): t for t in tasks_metadata
        }

        for future in as_completed(future_to_meta):
            meta = future_to_meta[future]
            count += 1
            try:
                # Retrieve the result from the thread
                season_stats = future.result()

                # Combine metadata with the fetched statistics
                entry = {"meta": meta, "stats": season_stats}
                database.append(entry)
                log.info(f"[{count}/{total}] OK: {meta['competition_name']} {meta['season_name']}")
            except Exception as e:
                log.error(f"[{count}/{total}] Error: {meta['competition_name']}: {e}")

    return database


def save_database_to_json(database: list[dict[str, Any]], filename: str) -> None:
    """
    Save the processed database to a JSON file in the 'data' directory.

    :param database: The list of processed data entries to save
    :param filename: The name of the output JSON file
    """
    # Resolve the path relative to the current script location
    current_dir = os.path.dirname(__file__)
    data_dir = os.path.join(current_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path = os.path.join(data_dir, filename)

    log.info(f"Saving database to: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False)


def aggregate_statistics(database: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """
    Flatten the granular database into a single aggregated dictionary.

    :param database: The source list of processed season entries
    :return: Aggregated stats mapping {position: {'passes': x, 'minutes': y}}
    """
    log.info("Aggregating statistics...")
    aggregated: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"passes": 0, "minutes": 0})

    # Sum up passes and minutes across all seasons in the database
    for entry in database:
        stats = entry["stats"]
        for position, values in stats.items():
            aggregated[position]["passes"] += values["passes"]
            aggregated[position]["minutes"] += values["minutes"]

    return aggregated


def run() -> int:
    """
    Run the main offline data processing pipeline.

    Steps:
      1. Fetch and filter competitions.
      2. Process data concurrently.
      3. Save results to JSON.
      4. Visualize aggregated data.

    :return: Exit code (0 = success, 1 = error)
    """
    log.info("Pipeline start - offline database mode")

    # 1. Fetch & Filter
    tasks_metadata = fetch_and_filter_seasons(START_YEAR, END_YEAR, TARGET_COMP_IDS)

    if not tasks_metadata:
        log.warning("No seasons found to process — exiting")
        return 1

    log.info(f"Selected seasons count: {len(tasks_metadata)}")

    # 2. Process Data (Download and compute stats)
    granular_database = build_granular_database(tasks_metadata)

    if not granular_database:
        log.error("Database is empty after processing — exiting")
        return 1

    # 3. Save Data (Persist to disk)
    save_database_to_json(granular_database, DB_FILENAME)

    # 4. Visualize Results (Aggregate and draw)
    aggregated_stats = aggregate_statistics(granular_database)

    log.info("Rendering summary and plots")
    draw_plots(aggregated_stats)
    print_summary(aggregated_stats, get_match_counter())

    log.info("Pipeline complete")
    return 0
