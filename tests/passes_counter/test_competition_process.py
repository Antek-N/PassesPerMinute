from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import pytest

from passes_per_minute.passes_counter.competition_processor import (
    _aggregate_positions,
    _drain_results_loop,
    _empty_stats,
    _extract_match_ids,
    _fetch_matches,
    _handle_error_or_retry,
    _submit_all_tasks,
    get_match_counter,
    process_competition,
)

"""
========================================================================================================================
_empty_stats
========================================================================================================================
"""


class TestEmptyStats:
    # Checks the structure of the resulting dictionary and default values for unknown keys.
    # Expectation: defaultdict with a factory returning {"passes": 0, "minutes": 0} for each role/position.
    def test_structure_and_defaults(self) -> None:
        stats = _empty_stats()
        # Initially, there should be no "Unknown" key
        assert "Unknown" not in stats
        # Accessing a non-existing key creates an entry with the default structure
        stats["Unknown"]
        assert stats["Unknown"] == {"passes": 0, "minutes": 0}
        # Modifying values of a specific key ("GK") works like a regular nested dict
        stats["GK"]["passes"] += 3
        stats["GK"]["minutes"] += 10
        assert stats["GK"] == {"passes": 3, "minutes": 10}


"""
========================================================================================================================
_fetch_matches
========================================================================================================================
"""


class TestFetchMatches:
    # Success: the function constructs a valid StatsBomb Open Data URL and returns a list of matches (passthrough from get_json).
    def test_successful_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sample = [{"match_id": 1}, {"match_id": 2}]
        called = {}

        # Replace get_json with a version that records the URL and returns the sample
        def fake_get_json(url: str) -> list[dict]:
            called["url"] = url
            return sample

        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_processor.get_json", fake_get_json)

        # The call should return exactly sample and use the expected URL
        out = _fetch_matches(9, 2020)
        assert out == sample
        assert called["url"] == "https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/9/2020.json"

    # I/O/HTTP error: exception from get_json should propagate (not be caught).
    def test_fetch_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(_url: str) -> None:
            raise RuntimeError("network down")

        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_processor.get_json", boom)

        with pytest.raises(RuntimeError):
            _fetch_matches(9, 2020)


"""
========================================================================================================================
_extract_match_ids
========================================================================================================================
"""


class TestExtractMatchIds:
    # Extracts match IDs from a list of dicts – preserving order and types (int).
    def test_extracts_ids(self) -> None:
        matches = [{"match_id": 10, "x": 1}, {"match_id": 11}]
        ids = _extract_match_ids(matches)
        assert ids == [10, 11]
        assert all(isinstance(i, int) for i in ids)

    # Empty input list => empty output list.
    def test_empty(self) -> None:
        assert _extract_match_ids([]) == []


"""
========================================================================================================================
_submit_all_tasks
========================================================================================================================
"""


class TestSubmitAllTasks:
    # Submitting tasks to ThreadPoolExecutor: creates one future per match_id
    # and calls MATCH_PROCESSOR.process_match for all IDs.
    def test_creates_futures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = []

        # Fake process_match: records the match_id and returns a minimal position structure
        def fake_process_match(mid: int) -> dict[str, dict[str, int]]:
            called.append(mid)
            return {"GK": {"passes": 0, "minutes": 0}}

        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor.MATCH_PROCESSOR.process_match",
            fake_process_match,
        )

        match_ids = [1, 2, 3]
        # Use a real executor but fake function – futures should be created
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = _submit_all_tasks(executor, match_ids)

        assert len(futures) == 3
        # Ensure each ID was passed to process_match
        assert sorted(called) == [1, 2, 3]


"""
========================================================================================================================
_aggregate_positions
========================================================================================================================
"""


class TestAggregatePositions:
    # Aggregates partial position stats (passes/minutes) into an accumulator.
    def test_aggregates(self) -> None:
        total = _empty_stats()
        partial_a = {"GK": {"passes": 5, "minutes": 90}, "CB": {"passes": 10, "minutes": 90}}
        partial_b = {"GK": {"passes": 2, "minutes": 45}, "LB": {"passes": 3, "minutes": 30}}

        # Two aggregations – values should sum by keys
        _aggregate_positions(total, partial_a)
        _aggregate_positions(total, partial_b)

        assert total["GK"] == {"passes": 7, "minutes": 135}
        assert total["CB"] == {"passes": 10, "minutes": 90}
        assert total["LB"] == {"passes": 3, "minutes": 30}


"""
========================================================================================================================
_handle_error_or_retry
========================================================================================================================
"""


class TestHandleErrorOrRetry:
    # If attempts < MAX_MATCH_RETRIES, an error should trigger task resubmission (retry).
    def test_resubmits_when_under_retry_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set low retry limit for testing
        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_processor.MAX_MATCH_RETRIES", 3)

        class FakeFuture:
            pass

        class FakeExecutor:
            def __init__(self) -> None:
                self.calls = 0

            # submit should be called with the proper match_id and return a Future
            def submit(self, fn: object, match_id: int) -> "FakeFuture":
                self.calls += 1
                assert match_id == 42
                return FakeFuture()

        fake_executor = FakeExecutor()
        futures = {}
        # attempts: counter of tries per match_id
        attempts = defaultdict(int)

        # After ValueError, expect one retry submission
        _handle_error_or_retry(fake_executor, futures, attempts, 42, ValueError("oops"))
        assert fake_executor.calls == 1
        assert attempts[42] == 1
        assert len(futures) == 1
        assert list(futures.keys())[0].__class__.__name__ == "FakeFuture"

    # When attempts exceed the limit, the function should raise RuntimeError mentioning match_id.
    def test_raises_after_exceeding_retry_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_processor.MAX_MATCH_RETRIES", 1)

        class FakeExecutor:
            def submit(self, fn: object, match_id: int) -> object:
                raise AssertionError("should not be called when max reached")

        futures = {}
        # Pre-set attempt counter to 1 (equal to MAX), so next error -> exception
        attempts = defaultdict(int)
        attempts[99] = 1

        with pytest.raises(RuntimeError, match="Failed to process match 99"):
            _handle_error_or_retry(FakeExecutor(), futures, attempts, 99, ValueError("x"))


"""
========================================================================================================================
_drain_results_loop
========================================================================================================================
"""


class TestDrainResultsLoop:
    # Scenario: one task succeeds immediately, the other fails once then succeeds after a single retry.
    # Expect correct aggregation.
    def test_success_with_single_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"A": 0, "B": 0}

        def fake_process_match(match_id: int) -> dict[str, dict[str, int]]:
            if match_id == 1:
                calls["A"] += 1
                return {"GK": {"passes": 1, "minutes": 90}}
            if match_id == 2:
                calls["B"] += 1
                if calls["B"] == 1:
                    # First call raises an error to trigger retry
                    raise ValueError("temporary")
                return {"CB": {"passes": 2, "minutes": 90}}
            raise AssertionError("unexpected id")

        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor.MATCH_PROCESSOR.process_match",
            fake_process_match,
        )

        positions = _empty_stats()
        # Create initial futures and let _drain_results_loop handle completion + retry
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            futures.update(
                {
                    executor.submit(fake_process_match, 1): 1,
                    executor.submit(fake_process_match, 2): 2,
                }
            )
            _drain_results_loop(executor, futures, positions)

        # After processing: GK from match 1, CB from match 2 (after retry)
        assert positions["GK"] == {"passes": 1, "minutes": 90}
        assert positions["CB"] == {"passes": 2, "minutes": 90}
        # Check number of calls – 1 for A, >=2 for B (error + retry)
        assert calls["A"] == 1
        assert calls["B"] >= 2

    # When all retries for a task are exhausted, the loop should stop and raise RuntimeError.
    def test_raises_when_retries_exhausted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_processor.MAX_MATCH_RETRIES", 1)

        def always_fails(_match_id: int) -> None:
            raise ValueError("nope")

        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor.MATCH_PROCESSOR.process_match",
            always_fails,
        )

        positions = _empty_stats()
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(always_fails, 7): 7}
            with pytest.raises(RuntimeError, match="Failed to process match 7"):
                _drain_results_loop(executor, futures, positions)


"""
========================================================================================================================
get_match_counter
========================================================================================================================
"""


class TestGetMatchCounter:
    # Public proxy – should simply delegate to MATCH_PROCESSOR.get_match_counter.
    def test_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_get() -> int:
            return 123

        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor.MATCH_PROCESSOR.get_match_counter",
            fake_get,
        )
        assert get_match_counter() == 123


"""
========================================================================================================================
process_competition
========================================================================================================================
"""


class TestProcessCompetition:
    # “Happy path” end-to-end: fetch matches, process 3 matches, and correctly aggregate positions.
    def test_end_to_end_aggregation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Fake fetch – return 3 matches
        def fake_fetch_matches(comp_id: int, season_id: int) -> list[dict[str, int]]:
            assert comp_id == 9 and season_id == 2020
            return [{"match_id": 1}, {"match_id": 2}, {"match_id": 3}]

        # Fake processor – different positions and values for 3 matches
        def fake_process_match(mid: int) -> dict[str, dict[str, int]]:
            if mid == 1:
                return {"GK": {"passes": 5, "minutes": 90}}
            if mid == 2:
                return {"GK": {"passes": 7, "minutes": 90}, "CB": {"passes": 3, "minutes": 45}}
            if mid == 3:
                return {"CB": {"passes": 2, "minutes": 50}}
            raise AssertionError("unexpected id")

        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor._fetch_matches",
            fake_fetch_matches,
        )
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor.MATCH_PROCESSOR.process_match",
            fake_process_match,
        )

        # Expected sum: GK (5+7, min 90+90) and CB (3+2, min 45+50)
        positions = process_competition(9, 2020)

        assert positions["GK"] == {"passes": 12, "minutes": 180}
        assert positions["CB"] == {"passes": 5, "minutes": 95}

    # No matches: result should be an empty dict (after conversion from defaultdict).
    def test_no_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Fake fetch – no matches
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor._fetch_matches",
            lambda _c, _s: [],
        )
        # Fake submit – no futures created
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_processor._submit_all_tasks",
            lambda executor, ids: {},
        )
        out = process_competition(1, 1)
        assert dict(out) == {}
