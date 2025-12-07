import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa E402
import pytest  # noqa E402
from matplotlib.axes import Axes  # noqa E402
from matplotlib.container import BarContainer  # noqa E402
from matplotlib.figure import Figure  # noqa E402

import passes_per_minute.plotter.bar_chart as bar  # noqa: E402

"""
========================================================================================================================
_validate
========================================================================================================================
"""


class TestValidate:
    def test_valid_mapping(self):
        # Valid mappings {str: number} should not raise any errors
        bar._validate({"Goalkeeper": 0.1, "Center Back": 0})
        bar._validate({"GK": 1})

    @pytest.mark.parametrize("bad", [None, 123, ["a"], ("a",), {1, 2}])
    def test_non_mapping_raises(self, bad):
        # Non-mapping input -> ValueError
        with pytest.raises(ValueError, match="mapping"):
            bar._validate(bad)  # type: ignore[arg-type]

    def test_non_string_keys_raise(self):
        # Keys that are not strings -> ValueError
        with pytest.raises(ValueError, match="keys.*strings"):
            bar._validate({1: 0.2})  # type: ignore[dict-item]

    def test_non_numeric_values_raise(self):
        # Values that are not int/float -> ValueError
        with pytest.raises(ValueError, match="int or float"):
            bar._validate({"Goalkeeper": object()})  # type: ignore[arg-type]


"""
========================================================================================================================
_prepare_data
========================================================================================================================
"""


class TestPrepareData:
    def test_fills_missing_and_sorts_desc(self):
        # Missing positions are filled with zeros; everything is sorted descending
        values = {"Center Back": 0.5, "Goalkeeper": 0.1}
        positions, vals = bar._prepare_data(values)

        assert isinstance(positions, tuple)
        assert isinstance(vals, tuple)
        assert len(positions) == len(bar.POSITIONS)
        assert len(vals) == len(bar.POSITIONS)

        # CB (0.5) should come before GK (0.1) after descending sort
        idx_cb = positions.index("Center Back")
        idx_gk = positions.index("Goalkeeper")
        assert vals[idx_cb] >= vals[idx_gk]

        # All missing positions should have value 0.0
        for pos in bar.POSITIONS:
            if pos not in values:
                assert vals[positions.index(pos)] == 0.0

    def test_empty_input_ok(self):
        # Empty input -> all positions filled with 0.0
        positions, vals = bar._prepare_data({})  # type: ignore[arg-type]
        assert len(positions) == len(bar.POSITIONS)
        assert all(v == 0.0 for v in vals)


"""
========================================================================================================================
_create_chart
========================================================================================================================
"""


class TestCreateChart:
    def test_returns_matplotlib_objects(self):
        # Prepare simple bar chart data
        positions = ["A", "B", "C"]
        vals = [0.2, 0.1, 0.3]

        # Call the function creating the chart
        fig, ax, bars = bar._create_chart(positions, vals)

        # Check that proper matplotlib objects were returned
        assert isinstance(fig, Figure)
        assert isinstance(ax, Axes)
        assert isinstance(bars, BarContainer)

        # Number of bars should match number of positions
        assert len(bars.patches) == 3

        # Close the figure after test
        plt.close(fig)


"""
========================================================================================================================
_annotate_bars
========================================================================================================================
"""


class TestAnnotateBars:
    def test_adds_one_text_per_bar(self):
        # Prepare a simple bar chart
        positions = ["A", "B"]
        vals = [0.12, 0.34]
        fig, ax = plt.subplots()
        bars = ax.bar(positions, vals)

        # Before adding labels, there should be no text elements
        assert len(ax.texts) == 0

        # Function should add one label above each bar
        bar._annotate_bars(ax, bars, vals)
        assert len(ax.texts) == len(vals)

        # Close figure after test to free resources
        plt.close(fig)


"""
========================================================================================================================
_style_chart
========================================================================================================================
"""


class TestStyleChart:
    def test_applies_style(self):
        # Prepare a simple chart with three bars
        positions = ["P1", "P2", "P3"]
        vals = [1, 2, 3]
        fig, ax = plt.subplots()
        ax.bar(positions, vals)

        # Call the chart styling function
        bar._style_chart(ax, positions, "My Title")

        # Check title and axis labels
        assert ax.get_title() == "My Title"
        assert ax.get_ylabel() == "Values"
        assert ax.get_xlabel() == "Positions"

        # Number of ticks should match number of positions
        assert len(ax.get_xticks()) == len(positions)
        ticklabels = ax.get_xticklabels()
        assert len(ticklabels) == len(positions)

        # Each label should be rotated 45° and right-aligned
        for lbl in ticklabels:
            assert pytest.approx(lbl.get_rotation(), rel=0, abs=1e-6) == 45.0
            assert lbl.get_ha() == "right"

        # Close figure after test
        plt.close(fig)


"""
========================================================================================================================
plot_bar_chart
========================================================================================================================
"""


class TestPlotBarChart:
    def test_happy_path(self, monkeypatch):
        # Disable chart display to prevent opening a window during tests
        monkeypatch.setattr(plt, "show", lambda: None)

        # Input data: two positions with different values
        values = {"Goalkeeper": 0.1, "Center Back": 0.5}

        # Call main chart plotting function
        fig, ax, bars = bar.plot_bar_chart(values, title="Average Passes per Minute by Position")

        # Verify that correct matplotlib objects are returned
        assert isinstance(fig, Figure)
        assert isinstance(ax, Axes)
        assert isinstance(bars, BarContainer)

        # Number of bars should match number of all defined positions
        assert len(bars.patches) == len(bar.POSITIONS)

        # Close figure after test
        plt.close(fig)

    def test_invalid_input_raises(self, monkeypatch):
        # Disable real rendering
        monkeypatch.setattr(plt, "show", lambda: None)

        # Invalid data (string value instead of number) should raise ValueError
        with pytest.raises(ValueError):
            bar.plot_bar_chart({"GK": "bad"})  # type: ignore[arg-type]
