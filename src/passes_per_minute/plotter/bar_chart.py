import logging
from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.container import BarContainer
from matplotlib.figure import Figure

log = logging.getLogger(__name__)

# Constant list of positions (order used to fill missing data and for sorting)
POSITIONS = [
    "Goalkeeper",
    "Center Back",
    "Left Center Back",
    "Right Center Back",
    "Left Back",
    "Right Back",
    "Left Wing Back",
    "Right Wing Back",
    "Center Defensive Midfield",
    "Left Defensive Midfield",
    "Right Defensive Midfield",
    "Center Midfield",
    "Left Center Midfield",
    "Right Center Midfield",
    "Left Midfield",
    "Right Midfield",
    "Center Attacking Midfield",
    "Left Attacking Midfield",
    "Right Attacking Midfield",
    "Left Wing",
    "Right Wing",
    "Center Forward",
    "Left Center Forward",
    "Right Center Forward",
    "Secondary Striker",
]


def _validate(values: Mapping[str, float]) -> None:
    """
    Validate the input mapping.

    :param values: Mapping of {str: float} representing positions and values
    :return: None
    """
    # check if the object is a mapping (e.g. dict)
    if not isinstance(values, Mapping):
        raise ValueError("values must be a mapping of {str: float}.")

    # iterate through all key-value pairs
    for key, value in values.items():
        # key must be a string (position name)
        if not isinstance(key, str):
            raise ValueError("All keys in values must be strings.")
        # value must be a number (int or float)
        if not isinstance(value, int | float):
            raise ValueError(f"Value for '{key}' must be int or float.")


def _prepare_data(values: Mapping[str, float]) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """
    Prepare data for plotting: validate, fill missing positions with zeros, and sort.

    :param values: Mapping of {str: float}
    :return: Two tuples (positions, values)
    """
    # validate input (keys = str, values = numbers)
    _validate(values)

    # build dictionary {position: value}, filling missing positions with zeros
    data = {pos: float(values.get(pos, 0.0)) for pos in POSITIONS}

    # sort data in descending order by value
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)

    # if there are no positions, raise an error
    if not sorted_data:
        raise ValueError("No positions to plot.")

    # split list of tuples [(pos, val), ...] into two tuples: (pos1, pos2, ...), (val1, val2, ...)
    positions, vals = zip(*sorted_data, strict=False)

    # return tuples (not iterators), so they can be reused
    return positions, vals


def _create_chart(positions: Sequence[str], vals: Sequence[float]) -> tuple[Figure, Axes, BarContainer]:
    """
    Create a bar chart with given positions and values.

    :param positions: Sequence of position names
    :param vals: Sequence of values
    :return: (Figure, Axes, BarContainer)
    """
    # create a new matplotlib figure and axes with given size
    fig, ax = plt.subplots(figsize=(12, 8))

    # draw bar chart for positions and values
    bars = ax.bar(positions, vals, color="skyblue", edgecolor="black")

    # return figure, axes, and bars collection
    return fig, ax, bars


def _annotate_bars(ax: Axes, bars: BarContainer, vals: Sequence[float]) -> None:
    """
    Annotate bars with numeric values above them.

    :param ax: Axes object
    :param bars: BarContainer object
    :param vals: Sequence of values
    :return: None
    """
    # iterate over each bar and its value
    for bar, value in zip(bars, vals, strict=False):
        # add text above the bar:
        # - X position = center of the bar
        # - Y position = bar height + small offset
        # - show value with two decimals
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{value:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )


def _style_chart(ax: Axes, positions: Sequence[str], title: str) -> None:
    """
    Apply styling to the bar chart.

    :param ax: Axes object
    :param positions: Sequence of position names
    :param title: Chart title
    :return: None
    """
    # set chart title
    ax.set_title(title, fontsize=16)

    # axis labels
    ax.set_ylabel("Values", fontsize=12)
    ax.set_xlabel("Positions", fontsize=12)

    # set X-axis ticks to match the number of positions
    ax.set_xticks(range(len(positions)))

    # set X-axis labels: position names, rotated 45 degrees for readability
    ax.set_xticklabels(positions, rotation=45, ha="right", fontsize=10)


def plot_bar_chart(
    values: Mapping[str, float], title: str = "Bar Chart of Position Values"
) -> tuple[Figure, Axes, BarContainer]:
    """
    Plot a bar chart of position values.

    :param values: Mapping {position: value}
    :param title: Title of the chart
    :return: (Figure, Axes, BarContainer)
    """
    log.info(f"Plot bar chart start positions_input={len(values)} title='{title}'")  # Log start
    try:
        # prepare data: validation, fill missing positions, sort
        positions, vals = _prepare_data(values)
        log.info(f"Data prepared positions={len(positions)}")  # Log success

        # create base bar chart
        fig, ax, bars = _create_chart(positions, vals)

        # add labels above bars
        _annotate_bars(ax, bars, vals)

        # set chart title and axis labels
        _style_chart(ax, positions, title)

        # adjust layout (prevent overlap)
        plt.tight_layout()

        # show chart
        # plt.show()
        log.info("Bar chart rendered")  # Log success

        # return matplotlib objects (figure, axes, bars)
        return fig, ax, bars
    except Exception:
        log.exception("Plot bar chart FAILED")  # Log failure
        raise
