import logging

import matplotlib.pyplot as plt

from passes_per_minute.plotter import plot_bar_chart, plot_pitch_chart

log = logging.getLogger(__name__)


def calculate_average_passes(positions: dict[str, dict[str, int]]) -> list[tuple[str, float]]:
    """
    Calculate the average number of passes per minute for each position.

    :param positions: A dictionary where the keys are position names and the values
                      are dictionaries with keys "passes" (int) and "minutes" (int).
    :return: A list of tuples [(position, average_passes_per_minute), ...],
             sorted in descending order by the average value.
    """
    # list of results: [(position, average_passes_per_minute), ...]
    summary = []

    for position, stats in positions.items():
        # calculate average only if minutes > 0
        if stats["minutes"] > 0:
            value = stats["passes"] / stats["minutes"]
        else:
            value = 0
        # add pair (position, average)
        summary.append((position, value))

    # sort descending by average value
    return sorted(summary, key=lambda x: x[1], reverse=True)


def print_summary(positions: dict[str, dict[str, int]], total_matches: int) -> None:
    """
    Print a textual summary of match statistics, including:
      - total number of matches processed,
      - passes and minutes per position,
      - average passes per minute by position.

    :param positions: A dictionary where the keys are position names and the values
                      are dictionaries with keys "passes" (int) and "minutes" (int).
    :param total_matches: The total number of processed matches.
    :return: None. Prints the summary to stdout.
    """
    log.info(f"Print summary start positions={len(positions)} total_matches={total_matches}")  # Log start
    if not positions:
        log.warning("No positions provided for summary")  # Log no data

    # print number of processed matches
    print(f"\nTotal matches processed: {total_matches}")

    # raw statistics for each position
    print("\nPosition Statistics:")
    for position, stats in positions.items():
        print(f"Position: {position}, Passes: {stats['passes']}, Minutes: {stats['minutes']}")

    # calculate average passes per minute and print them sorted in descending order
    summary = calculate_average_passes(positions)
    print("\nAverage Passes per Minute by Position:")
    for position, avg in summary:
        print(f"{position}: {avg:.5f}")

    log.info("Print summary complete")  # Log success


def draw_plots(positions: dict[str, dict[str, int]]) -> None:
    """
    Generate visualizations of passes per minute by position, including:
      - a football pitch heatmap,
      - a bar chart.

    :param positions: A dictionary where the keys are position names and the values
                      are dictionaries with keys "passes" (int) and "minutes" (int).
    :return: None. Displays plots using the `plots` module.
    """
    # calculate average passes per minute and take them as a sorted list
    data = calculate_average_passes(positions)
    if not data:
        log.warning("No data to plot")  # Log no data
        return

    # convert list [(position, value)] to dictionary {position: value}
    dict_for_plots = {position: value for position, value in data}

    log.info(f"Drawing plots positions={len(dict_for_plots)}")  # Log start
    try:
        # draw a pitch heatmap with values for positions
        plot_bar_chart(dict_for_plots, "Average Passes per Minute by Position")

        # draw a bar chart of average passes per minute
        plot_pitch_chart(dict_for_plots, "Average Passes per Minute by Position")

        plt.show()

        log.info("Plots rendered")  # Log success
    except Exception:
        log.exception("Plot rendering FAILED")  # Log failure
        raise
