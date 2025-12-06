from collections import defaultdict

from passes_per_minute.passes_counter.match_processor import MatchProcessor

"""
========================================================================================================================
_extract_starting_xi
========================================================================================================================
"""


class TestExtractStartingXI:
    # Creates entries with open intervals starting from minute 0
    def test_initializes_intervals(self):
        mp = MatchProcessor()
        player_positions = {}

        # "Starting XI" event with two players and their positions
        event = {
            "type": {"name": "Starting XI"},
            "tactics": {
                "lineup": [
                    {"player": {"id": 1}, "position": {"name": "GK"}},
                    {"player": {"id": 2}, "position": {"name": "CB"}},
                ]
            },
        }

        # Process the event — the method should initialize the players
        mp._extract_starting_xi(event, player_positions)

        # Verify that entries were created for both players
        assert list(player_positions.keys()) == [1, 2]

        # Each player should have an open interval starting at minute 0
        assert player_positions[1] == [{"position": "GK", "start_time": 0, "end_time": None}]
        assert player_positions[2] == [{"position": "CB", "start_time": 0, "end_time": None}]


"""
========================================================================================================================
_handle_substitution
========================================================================================================================
"""


class TestHandleSubstitution:
    # Closes the OUT player’s interval and opens a new one for the IN player with the same position
    def test_handles_normal_substitution(self):
        mp = MatchProcessor()
        # Initially, player 10 plays as CB from minute 0
        player_positions = {
            10: [{"position": "CB", "start_time": 0, "end_time": None}],
        }

        # Substitution event – player 10 OUT, player 11 IN at minute 60
        event = {
            "type": {"name": "Substitution"},
            "player": {"id": 10},  # OUT
            "substitution": {"replacement": {"id": 11}},  # IN
            "minute": 60,
        }

        # Process the substitution
        mp._handle_substitution(event, player_positions)

        # Player 10’s interval should be closed at minute 60
        assert player_positions[10][-1]["end_time"] == 60
        # Player 11 should start playing in the same position at minute 60
        assert player_positions[11] == [{"position": "CB", "start_time": 60, "end_time": None}]

    # If the OUT player wasn’t tracked – do nothing (just log)
    def test_ignores_when_player_out_unknown(self):
        mp = MatchProcessor()

        # No tracked players — player_positions is empty
        player_positions = {}

        # Substitution event – player 99 OUT, player 77 IN at minute 12
        event = {
            "type": {"name": "Substitution"},
            "player": {"id": 99},
            "substitution": {"replacement": {"id": 77}},
            "minute": 12,
        }

        # Since player 99 wasn’t tracked, the method should do nothing
        mp._handle_substitution(event, player_positions)

        # Verify the dictionary remains empty
        assert player_positions == {}


"""
========================================================================================================================
_update_player_positions
========================================================================================================================
"""


class TestUpdatePlayerPositions:
    # Position change closes old interval and opens a new one
    def test_changes_position_creates_new_interval(self):
        mp = MatchProcessor()
        # Player 5 starts the match as LB from minute 0
        player_positions = {
            5: [{"position": "LB", "start_time": 0, "end_time": None}],
        }

        # At minute 23, the player changes position to LWB
        event = {"player": {"id": 5}, "position": {"name": "LWB"}, "minute": 23}

        # Process the position change event
        mp._update_player_positions(event, player_positions)

        # The previous interval (LB) should be closed at minute 23
        assert player_positions[5][0]["end_time"] == 23

        # A new interval (LWB) should start at minute 23
        assert player_positions[5][1] == {"position": "LWB", "start_time": 23, "end_time": None}

    # Missing "position" key in event – do nothing
    def test_no_position_key_does_nothing(self):
        mp = MatchProcessor()
        # Player 3 is tracked as CM from minute 0
        player_positions = {3: [{"position": "CM", "start_time": 0, "end_time": None}]}
        # Event without a "position" field — no position change info
        event = {"player": {"id": 3}, "minute": 10}

        # Method should not modify state
        mp._update_player_positions(event, player_positions)

        # Interval remains unchanged
        assert player_positions[3] == [{"position": "CM", "start_time": 0, "end_time": None}]

    # If player is not tracked – do nothing
    def test_player_not_tracked_does_nothing(self):
        mp = MatchProcessor()
        # No entry for player 44
        player_positions = {}
        # Event with position, but player not tracked yet
        event = {"player": {"id": 44}, "position": {"name": "RW"}, "minute": 15}

        # Method should not modify anything
        mp._update_player_positions(event, player_positions)

        # Dictionary remains empty
        assert player_positions == {}


"""
========================================================================================================================
_finalize_process
========================================================================================================================
"""


class TestFinalizeProcess:
    # Closes open intervals at max(minute) from events; sums minutes per position
    def test_closes_open_intervals_and_sums_minutes(self):
        mp = MatchProcessor()
        match_positions = defaultdict(lambda: {"passes": 0, "minutes": 0})
        # Player 1: full 90 mins as GK
        # Player 2: 0–30 as CB, 30–(open) as RB
        player_positions = {
            1: [{"position": "GK", "start_time": 0, "end_time": 90}],
            2: [
                {"position": "CB", "start_time": 0, "end_time": 30},
                {"position": "RB", "start_time": 30, "end_time": None},  # open
            ],
        }
        # Last minute of match is 92 (max from events)
        events = [{"minute": 10}, {"minute": 50}, {"minute": 92}]

        # Close intervals and sum minutes per position
        mp._finalize_process(player_positions, match_positions, events)

        # GK: 90 minutes
        assert match_positions["GK"]["minutes"] == 90
        # CB: 30-0 = 30; RB: 92-30 = 62
        assert match_positions["CB"]["minutes"] == 30
        assert match_positions["RB"]["minutes"] == 62

    # When no events – close at 90 by default
    def test_no_events_defaults_to_90(self):
        mp = MatchProcessor()
        match_positions = defaultdict(lambda: {"passes": 0, "minutes": 0})
        # Open interval from minute 10, no events => default close at 90
        player_positions = {7: [{"position": "LW", "start_time": 10, "end_time": None}]}

        mp._finalize_process(player_positions, match_positions, events=[])

        # 90 - 10 = 80 minutes
        assert match_positions["LW"]["minutes"] == 80

    # Negative minutes → clamp to zero
    def test_negative_minutes_are_clamped_to_zero(self):
        mp = MatchProcessor()
        match_positions = defaultdict(lambda: {"passes": 0, "minutes": 0})
        # Invalid data: end_time < start_time
        player_positions = {8: [{"position": "CM", "start_time": 50, "end_time": 30}]}

        # Function should correct result to 0
        mp._finalize_process(player_positions, match_positions, events=[{"minute": 60}])

        assert match_positions["CM"]["minutes"] == 0


"""
========================================================================================================================
_aggregate_pass_data
========================================================================================================================
"""


class TestAggregatePassData:
    # Counts passes within intervals [start, end)
    def test_counts_passes_within_intervals(self):
        mp = MatchProcessor()
        match_positions = defaultdict(lambda: {"passes": 0, "minutes": 0})
        # Player 10: 0–30 as CM, 30–60 as CAM
        player_positions = {
            10: [
                {"position": "CM", "start_time": 0, "end_time": 30},
                {"position": "CAM", "start_time": 30, "end_time": 60},
            ]
        }
        # Four passes within intervals + ignored events
        events = [
            {"type": {"name": "Pass"}, "player": {"id": 10}, "minute": 0},  # CM
            {"type": {"name": "Pass"}, "player": {"id": 10}, "minute": 29},  # CM
            {"type": {"name": "Pass"}, "player": {"id": 10}, "minute": 30},  # CAM (boundary)
            {"type": {"name": "Pass"}, "player": {"id": 10}, "minute": 59},  # CAM
            {"type": {"name": "Pass"}, "player": {"id": 999}, "minute": 10},  # untracked
            {"type": {"name": "Shot"}, "player": {"id": 10}, "minute": 15},  # not a pass
        ]

        # Count passes by position at given minute
        mp._aggregate_pass_data(events, match_positions, player_positions)

        # 2 passes as CM, 2 as CAM; others ignored
        assert match_positions["CM"]["passes"] == 2
        assert match_positions["CAM"]["passes"] == 2
        assert "Shot" not in match_positions  # no effect

    # Open interval (end_time=None) – event skipped until closed
    def test_open_interval_is_skipped(self):
        mp = MatchProcessor()
        match_positions = defaultdict(lambda: {"passes": 0, "minutes": 0})
        # RW has an open interval — not yet closed
        player_positions = {5: [{"position": "RW", "start_time": 0, "end_time": None}]}
        events = [{"type": {"name": "Pass"}, "player": {"id": 5}, "minute": 10}]

        # Pass in open interval is ignored (will count after closed)
        mp._aggregate_pass_data(events, match_positions, player_positions)

        # Pass count remains unchanged
        assert match_positions["RW"]["passes"] == 0


"""
========================================================================================================================
process_match + get_match_counter
========================================================================================================================
"""


class TestProcessMatch:
    # Full flow on artificial data (mock get_json)
    def test_processes_events_and_increments_counter(self, monkeypatch):
        mp = MatchProcessor()

        # Sequence of events:
        # - Starting XI: player 1 (GK), player 2 (CB)
        # - Position change p2 -> RB at 15'
        # - Pass p2 at 20' (RB)
        # - Substitution: p2 OUT, p3 IN at 30' (RB)
        # - Two passes p3 at 40' and 70' (RB)
        # - End of match 80'
        events = [
            {
                "type": {"name": "Starting XI"},
                "tactics": {
                    "lineup": [
                        {"player": {"id": 1}, "position": {"name": "GK"}},
                        {"player": {"id": 2}, "position": {"name": "CB"}},
                    ]
                },
            },
            {"type": {"name": "Dummy"}, "player": {"id": 2}, "position": {"name": "RB"}, "minute": 15},
            {"type": {"name": "Pass"}, "player": {"id": 2}, "minute": 20},
            {
                "type": {"name": "Substitution"},
                "player": {"id": 2},
                "substitution": {"replacement": {"id": 3}},
                "minute": 30,
            },
            {"type": {"name": "Pass"}, "player": {"id": 3}, "minute": 40},
            {"type": {"name": "Pass"}, "player": {"id": 3}, "minute": 70},
            {"type": {"name": "Dummy"}, "minute": 80},
        ]

        # Mock data retrieval
        def fake_get_json(url):
            assert "events" in url
            return events

        monkeypatch.setattr("src.passes_per_minute.passes_counter.match_processor.get_json", fake_get_json)

        # Process the match
        out = mp.process_match(match_id=12345)

        # Minutes per position
        assert out["GK"]["minutes"] == 80  # p1: 0–80
        assert out["CB"]["minutes"] == 15  # p2: 0–15
        assert out["RB"]["minutes"] == 65  # p2: 15–30 (15) + p3: 30–80 (50)

        # Passes assigned to RB
        assert out["RB"]["passes"] == 3  # p2@20', p3@40', p3@70'
        assert out["GK"]["passes"] == 0
        assert out["CB"]["passes"] == 0

        # Match counter increased
        assert mp.get_match_counter() == 1

    # No Starting XI – function still works (counts nothing)
    def test_no_starting_xi_still_works(self, monkeypatch):
        mp = MatchProcessor()

        # Events without starting lineup
        events = [
            {"type": {"name": "Pass"}, "player": {"id": 10}, "minute": 5},  # unassigned (no position)
            {"type": {"name": "Dummy"}, "minute": 12},
            {"type": {"name": "Dummy"}, "minute": 30},
        ]

        # Stub `get_json`
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.match_processor.get_json",
            lambda _url: events,
        )

        # Process the match
        out = mp.process_match(match_id="X")

        # Without Starting XI there are no intervals → no minutes or passes
        assert dict(out) == {}
        assert mp.get_match_counter() >= 1  # counter incremented
