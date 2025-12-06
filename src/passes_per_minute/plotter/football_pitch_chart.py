import logging
import math
from collections.abc import Mapping

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

log = logging.getLogger(__name__)

# Constant coordinates of positions on the pitch (0–70 horizontally, 0–100 vertically)
POSITIONS = {
    "Goalkeeper": (35, 5),
    "Center Back": (35, 20),
    "Left Center Back": (25, 20),
    "Right Center Back": (45, 20),
    "Left Back": (15, 25),
    "Right Back": (55, 25),
    "Left Wing Back": (10, 35),
    "Right Wing Back": (60, 35),
    "Center Defensive Midfield": (35, 35),
    "Left Defensive Midfield": (25, 35),
    "Right Defensive Midfield": (45, 35),
    "Center Midfield": (35, 50),
    "Left Center Midfield": (25, 50),
    "Right Center Midfield": (45, 50),
    "Left Midfield": (15, 50),
    "Right Midfield": (55, 50),
    "Center Attacking Midfield": (35, 65),
    "Left Attacking Midfield": (25, 65),
    "Right Attacking Midfield": (45, 65),
    "Left Wing": (10, 75),
    "Right Wing": (60, 75),
    "Center Forward": (35, 85),
    "Left Center Forward": (25, 85),
    "Right Center Forward": (45, 85),
    "Secondary Striker": (35, 75),
}


def _validate(values: Mapping[str, float]) -> None:
    """
    Validate input mapping: must be {str: number}, values must be finite.

    :param values: input mapping
    :return: None
    """
    # check if input is a mapping (e.g., dict)
    if not isinstance(values, Mapping):
        raise ValueError("values must be a mapping of {str: float}.")

    # iterate over all key-value pairs
    for key, value in values.items():
        # key must be a string
        if not isinstance(key, str):
            raise ValueError("All keys must be strings.")

        # attempt to cast value to float
        try:
            float_value = float(value)
        except Exception as e:
            raise ValueError(f"Value for '{key}' must be a number.") from e

        # value must be finite (not NaN, not inf)
        if not math.isfinite(float_value):
            raise ValueError(f"Value for '{key}' must be a finite number.")


def _wrap_text(text: str, max_width: int = 15) -> str:
    """
    Wrap long text into multiple lines by word boundaries.

    :param text: input string
    :param max_width: max characters per line
    :return: wrapped string with newlines
    """
    # split text into words
    words = text.split()
    lines: list[str] = []
    current_line: list[str] = []

    for word in words:
        # check if adding the word would exceed max_width
        current_len = sum(map(len, current_line)) + len(current_line) + len(word)
        if current_len > max_width:
            # if so – close current line
            lines.append(" ".join(current_line))
            # start a new line with current word
            current_line = [word]
        else:
            # otherwise add word to current line
            current_line.append(word)

    # if buffer is not empty, append as last line
    if current_line:
        lines.append(" ".join(current_line))

    # return text with line breaks
    return "\n".join(lines)


def _draw_pitch(ax: Axes) -> None:
    """
    Draw football pitch outline on given axes.

    :param ax: matplotlib axes
    :return: None
    """
    # set axis limits (pitch 70x100)
    ax.set_xlim(0, 70)
    ax.set_ylim(0, 100)

    # draw sidelines and goal lines
    ax.plot([0, 0], [0, 100], color="green", zorder=1)  # left line
    ax.plot([70, 70], [0, 100], color="green", zorder=1)  # right line
    ax.plot([0, 70], [0, 0], color="green", zorder=1)  # bottom line
    ax.plot([0, 70], [100, 100], color="green", zorder=1)  # top line

    # halfway line
    ax.plot([0, 70], [50, 50], color="green", linestyle="--", zorder=1)

    # center circle (center = (35, 50), radius = 9)
    ax.add_artist(plt.Circle((35, 50), 9, color="green", fill=False, zorder=1))


def _draw_markers_and_text(ax: Axes, values: Mapping[str, float]) -> None:
    """
    Draw markers and text for each position on the pitch.

    :param ax: matplotlib axes
    :param values: mapping of {position: value}
    :return: None
    """
    # validate input data
    _validate(values)

    # prepare list of values in POSITIONS order
    all_values = [float(values.get(position, 0.0)) for position in POSITIONS.keys()]
    val_max = max(all_values) if all_values else 1.0  # max value (for scaling)
    val_min = min(all_values) if all_values else 0.0  # min value
    value_range = (val_max - val_min) if (val_max - val_min) != 0 else 1.0  # avoid division by zero

    if not values:
        log.warning("No values provided for pitch drawing")  # Log no data
    if val_max <= 0:
        log.warning("All values are <= 0; markers will use minimum size")  # Log edge case
    log.info(f"Pitch data range val_min={val_min:.4f} val_max={val_max:.4f}")  # Log stats

    # marker size parameters
    size_floor = 50.0  # minimum size
    size_scale = 500.0  # maximum scale

    # draw each marker based on pitch coordinates
    for position, (x, y) in POSITIONS.items():
        value = float(values.get(position, 0.0))

        # marker size proportional to value
        # size = base size + scaled value (normalized by val_max)
        size = size_floor + (0.0 if value <= 0 else (value / (val_max if val_max > 0 else 1.0)) * size_scale)

        # color based on normalized value (between val_min and val_max)
        norm = (value - val_min) / value_range
        color = matplotlib.colormaps["Reds"](norm)

        # draw circle at (x, y)
        ax.scatter(
            x,
            y,
            s=size,
            c=[color],
            edgecolors="black",
            linewidth=0.5,
            marker="o",
            zorder=2,
        )

        # add position label (slightly above marker)
        ax.text(x, y + 3, _wrap_text(position), fontsize=8, ha="center", zorder=3)

        # add numeric value (slightly below marker)
        ax.text(x, y - 3, f"{value:.2f}", fontsize=8, ha="center", color="black", zorder=3)


def plot_pitch_chart(values: Mapping[str, float], title: str = "Football Pitch Visualization") -> tuple[Figure, Axes]:
    """
    Plot football pitch chart with markers representing position values.

    :param values: mapping {position: value}
    :param title: chart title
    :return: (figure, axes)
    """
    log.info(f"Plot pitch chart start positions_input={len(values)} title='{title}'")  # Log start
    try:
        fig, ax = plt.subplots(figsize=(7, 10))  # create figure

        _draw_pitch(ax)  # draw pitch outline
        _draw_markers_and_text(ax, values)  # add markers and labels

        ax.axis("off")  # hide axes
        plt.title(title)
        plt.tight_layout()

        # plt.show()
        log.info("Pitch chart rendered")  # Log success

        return fig, ax
    except Exception:
        log.exception("Plot pitch chart FAILED")  # Log failure
        raise
