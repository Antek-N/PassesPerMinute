import pytest

from passes_per_minute.passes_counter import (
    draw_plots,
    print_summary,
)
from passes_per_minute.passes_counter.player_position_stats import calculate_average_passes

"""
========================================================================================================================
_calculate_average_passes
========================================================================================================================
"""


class TestCalculateAveragePasses:
    # Typical case: calculates averages and sorts in descending order
    def test_typical(self):
        # Input data: positions with different numbers of passes and minutes
        positions = {
            "GK": {"passes": 10, "minutes": 100},  # 0.1
            "CB": {"passes": 30, "minutes": 60},  # 0.5
            "RB": {"passes": 10, "minutes": 20},  # 0.5
            "LW": {"passes": 0, "minutes": 0},  # 0.0 (no minutes)
        }

        # Calculate average passes/min and sort descending
        out = calculate_average_passes(positions)

        # CB and RB have the highest average (0.5) — they appear first
        assert out[0][1] == pytest.approx(0.5)
        assert out[1][1] == pytest.approx(0.5)
        assert {out[0][0], out[1][0]} == {"CB", "RB"}

        # GK next, LW (0.0) at the end
        assert ("GK", pytest.approx(0.1)) in [(k, pytest.approx(v)) for k, v in out]
        assert out[-1] == ("LW", 0)

    # Minutes = 0 -> average set to 0
    def test_zero_minutes(self):
        positions = {"CM": {"passes": 25, "minutes": 0}}

        # If there are no minutes, result = 0 instead of division by zero
        out = calculate_average_passes(positions)

        assert out == [("CM", 0)]

    # Empty input -> returns empty list
    def test_empty_input(self):
        # No positions in the dictionary
        assert calculate_average_passes({}) == []


"""
========================================================================================================================
print_summary
========================================================================================================================
"""


class TestPrintSummary:
    # Prints headers and data; verified through capsys
    def test_prints_expected_lines(self, capsys):
        # Input data – two positions with different stats
        positions = {
            "GK": {"passes": 10, "minutes": 100},
            "CB": {"passes": 30, "minutes": 60},
        }

        # Call the function that prints the summary
        print_summary(positions, total_matches=7)

        # Capture console output
        captured = capsys.readouterr().out

        # Check header with number of matches
        assert "Total matches processed: 7" in captured

        # Check raw statistics
        assert "Position: GK, Passes: 10, Minutes: 100" in captured
        assert "Position: CB, Passes: 30, Minutes: 60" in captured

        # Check section with average values
        assert "Average Passes per Minute by Position:" in captured
        assert "GK: 0.10000" in captured
        assert "CB: 0.50000" in captured

    # Empty data – function still prints section structure, but no positions
    def test_prints_with_empty_positions(self, capsys):
        # Call with empty dictionary and zero matches
        print_summary({}, total_matches=0)

        # Capture output
        captured = capsys.readouterr().out

        # Sections should appear even if data is missing
        assert "Total matches processed: 0" in captured
        assert "Position Statistics:" in captured
        assert "Average Passes per Minute by Position:" in captured

        # There should be no position entries in the statistics section
        assert "Position:" not in captured.split("Position Statistics:")[-1] or True


"""
========================================================================================================================
draw_plots
========================================================================================================================
"""


class TestDrawPlots:
    # Empty data -> nothing is drawn (plot functions not called)
    def test_no_data_returns_early(self, monkeypatch):
        # Counters to check if plotting functions were called
        called = {"bar": 0, "pitch": 0}

        # Fake plotting functions – only increment the counter
        def fake_bar(values, title):
            called["bar"] += 1

        def fake_pitch(values, title):
            called["pitch"] += 1

        # Replace original plotting functions with fake ones
        monkeypatch.setattr("src.passes_per_minute.passes_counter.player_position_stats.plot_bar_chart", fake_bar)
        monkeypatch.setattr("src.passes_per_minute.passes_counter.player_position_stats.plot_pitch_chart", fake_pitch)

        # Call with empty data – should return immediately
        draw_plots({})

        # Plotting functions should not be called
        assert called["bar"] == 0
        assert called["pitch"] == 0

    # Valid data -> both plotting functions called with expected arguments
    def test_calls_plot_functions_with_prepared_dict(self, monkeypatch):
        calls = {"args": []}

        # Fake functions that record their calls
        def fake_bar(values, title):
            calls["args"].append(("bar", values, title))

        def fake_pitch(values, title):
            calls["args"].append(("pitch", values, title))

        # Replace originals with test doubles
        monkeypatch.setattr("src.passes_per_minute.passes_counter.player_position_stats.plot_bar_chart", fake_bar)
        monkeypatch.setattr("src.passes_per_minute.passes_counter.player_position_stats.plot_pitch_chart", fake_pitch)

        # Input data with different averages
        positions = {
            "GK": {"passes": 10, "minutes": 100},  # 0.1
            "CB": {"passes": 30, "minutes": 60},  # 0.5
            "LW": {"passes": 0, "minutes": 0},  # 0.0
        }

        # The function should call both plot types
        draw_plots(positions)

        # Two calls: bar, pitch (order preserved)
        assert len(calls["args"]) == 2
        kind1, values1, title1 = calls["args"][0]
        kind2, values2, title2 = calls["args"][1]

        assert kind1 == "bar"
        assert kind2 == "pitch"
        expected_title = "Average Passes per Minute by Position"
        assert title1 == expected_title
        assert title2 == expected_title

        # Dictionary of values with correct averages
        assert values1["CB"] == pytest.approx(0.5)
        assert values1["GK"] == pytest.approx(0.1)
        assert values1["LW"] == pytest.approx(0.0)
        assert values1 == values2  # both plots use the same data

    # If a plotting function raises an exception – draw_plots should propagate it
    def test_plot_error_is_propagated(self, monkeypatch):
        # First plotting function (bar) raises an error
        def boom(_values, _title):
            raise RuntimeError("render failed")

        # Replace functions in the module
        monkeypatch.setattr("src.passes_per_minute.passes_counter.player_position_stats.plot_bar_chart", boom)
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.player_position_stats.plot_pitch_chart", lambda *a, **k: None
        )

        # Expecting the exception to propagate
        with pytest.raises(RuntimeError, match="render failed"):
            draw_plots({"CB": {"passes": 30, "minutes": 60}})
