import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa E402
import pytest  # noqa E402

import passes_per_minute.plotter.football_pitch_chart as pitch  # noqa: E402

"""
========================================================================================================================
_validate
========================================================================================================================
"""


class TestValidate:
    def test_valid_mapping(self):
        # Correct input — dictionary {str: number} should not raise an error
        pitch._validate({"Goalkeeper": 0.1, "Center Back": 0})

    @pytest.mark.parametrize("bad", [None, 123, ["a"], ("a",), {1, 2}])
    def test_non_mapping_raises(self, bad):
        # Invalid data type (not a mapping) -> expected ValueError
        with pytest.raises(ValueError, match="mapping"):
            pitch._validate(bad)  # type: ignore[arg-type]

    def test_non_string_keys_raise(self):
        # Keys other than strings -> should raise ValueError
        with pytest.raises(ValueError, match="keys.*strings"):
            pitch._validate({1: 0.2})  # type: ignore[dict-item]

    def test_non_numeric_values_raise(self):
        # Value that is not a number (e.g., object) -> ValueError
        with pytest.raises(ValueError, match="number"):
            pitch._validate({"Goalkeeper": object()})  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_values_raise(self, bad):
        # Non-finite values (NaN, inf, -inf) -> ValueError
        with pytest.raises(ValueError, match="finite"):
            pitch._validate({"Goalkeeper": bad})


"""
========================================================================================================================
_wrap_text
========================================================================================================================
"""


class TestWrapText:
    def test_wraps_by_word_boundaries(self):
        # Long text should be wrapped without breaking words
        text = "Very Long Position Name That Should Wrap Nicely"
        wrapped = pitch._wrap_text(text, max_width=12)

        # No line should exceed the maximum width
        assert all(len(line) <= 12 for line in wrapped.split("\n"))
        # There should be at least one line break
        assert "\n" in wrapped

    def test_short_text_unchanged(self):
        # Short text should remain unchanged
        assert pitch._wrap_text("Short", max_width=50) == "Short"


"""
========================================================================================================================
_draw_pitch
========================================================================================================================
"""


class TestDrawPitch:
    def test_draws_outline_and_center_circle(self):
        # Create an empty plot and draw the pitch
        fig, ax = plt.subplots()
        pitch._draw_pitch(ax)

        # There should be at least 5 lines (four borders + center line)
        assert len(ax.lines) >= 5

        # The center circle should be added as a Circle object
        assert any(getattr(a, "__class__", None).__name__ == "Circle" for a in ax.artists + ax.patches)

        # Check correct axis limits corresponding to pitch dimensions
        assert ax.get_xlim() == (0, 70)
        assert ax.get_ylim() == (0, 100)

        # Close the figure after the test
        plt.close(fig)


"""
========================================================================================================================
_draw_markers_and_text
========================================================================================================================
"""


class TestDrawMarkersAndText:
    def test_draws_marker_and_labels_for_all_positions(self):
        # Create a new figure and axes
        fig, ax = plt.subplots()

        # Test data for a few positions — the rest will be filled with zeros
        values = {"Goalkeeper": 0.1, "Center Back": 0.5, "Left Wing": 0.3}

        # Draw markers and labels on the pitch
        pitch._draw_markers_and_text(ax, values)

        # There should be as many markers as positions in the POSITIONS dictionary
        assert len(ax.collections) == len(pitch.POSITIONS)

        # Each position should have two text labels — name and numeric value
        assert len(ax.texts) == 2 * len(pitch.POSITIONS)

        # Close the figure after the test
        plt.close(fig)

    def test_invalid_values_raise(self):
        # Invalid value (string instead of number) should raise an exception
        fig, ax = plt.subplots()
        with pytest.raises(ValueError):
            pitch._draw_markers_and_text(ax, {"Goalkeeper": "bad"})  # type: ignore[arg-type]
        plt.close(fig)


"""
========================================================================================================================
plot_pitch_chart
========================================================================================================================
"""


class TestPlotPitchChart:
    def test_happy_path(self, monkeypatch):
        # Disable actual plot display (so test doesn’t open a window)
        monkeypatch.setattr(plt, "show", lambda: None)

        # Test data for two positions
        values = {"Goalkeeper": 0.1, "Center Back": 0.5}

        # Call the function to draw the full pitch chart
        fig, ax = pitch.plot_pitch_chart(values, title="Football Pitch Visualization")

        # Check that valid matplotlib objects were created
        assert getattr(fig, "number", None) is not None
        assert ax is not None

        # There should be as many markers and labels as positions in POSITIONS
        assert len(ax.collections) == len(pitch.POSITIONS)
        assert len(ax.texts) == 2 * len(pitch.POSITIONS)

        # Close the figure after the test
        plt.close(fig)

    def test_invalid_input_propagates(self, monkeypatch):
        # Disable actual rendering
        monkeypatch.setattr(plt, "show", lambda: None)

        # Invalid value (NaN) -> expected ValueError from validation
        with pytest.raises(ValueError):
            pitch.plot_pitch_chart({"Goalkeeper": float("nan")})
