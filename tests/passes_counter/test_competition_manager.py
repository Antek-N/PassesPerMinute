import pytest

from passes_per_minute.passes_counter.competition_manager import (
    _generate_seasons_and_years,
    fetch_competitions,
    get_competition_seasons,
)

"""
========================================================================================================================
_fetch_competitions
========================================================================================================================
"""


class TestFetchCompetitions:
    # Success: checks if the get_json is called with the correct URL and returns data in the expected format (list of dicts)
    def test_successful_fetch(self, monkeypatch):
        # artificial response that fake should return instead of the real get_json
        sample = [
            {"competition_id": 9, "season_id": 1, "season_name": "2019/2020"},
            {"competition_id": 16, "season_id": 2, "season_name": "2020/2021"},
        ]
        # helper dict to record what URL the fake was called with
        called = {}

        # fake implementation of get_json – instead of fetching data from the network,
        # it records the URL and returns the prepared `sample` list
        def fake_get_json(url):
            called["url"] = url
            return sample

        # monkeypatch replaces the real get_json with our fake_get_json
        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_manager.get_json", fake_get_json)

        # call the function, which normally uses get_json,
        # but in the test it will use the patched fake_get_json
        out = fetch_competitions()

        # check that the result is a list
        assert isinstance(out, list)

        # and that the result is exactly our `sample`
        assert out == sample

        # and that the URL was exactly the expected one
        assert called["url"] == "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"

    # HTTP/IO error: exception is propagated further
    def test_fetch_failure_propagates(self, monkeypatch):
        # fake implementation of get_json that always raises an exception
        def raise_error(_url):
            raise RuntimeError("network down")

        # patch get_json, so it becomes raise_error() instead of the real one
        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_manager.get_json", raise_error)

        # check that fetch_competitions does not swallow the exception,
        # but propagates it further (pytest.raises expects that)
        with pytest.raises(RuntimeError):
            fetch_competitions()


"""
========================================================================================================================
_generate_seasons_and_years
========================================================================================================================
"""


class TestGenerateSeasonsAndYears:
    # Classic range of several years – returns a tuple with "YYYY/YYYY+1" and "YYYY"
    def test_range_multiple_years(self):
        # call the function for the range 2019–2021
        out = _generate_seasons_and_years(2019, 2021)

        # the result should be a tuple, not e.g. a list
        assert isinstance(out, tuple)

        # first part of the tuple (seasons in the form "YYYY/YYYY+1")
        # for 2019, 2020, 2021 > "2019/2020", "2020/2021", "2021/2022"
        assert out[:3] == ("2019/2020", "2020/2021", "2021/2022")

        # second part of the tuple (just years in the form "YYYY")
        # for 2019, 2020, 2021 > "2019", "2020", "2021"
        assert out[3:] == ("2019", "2020", "2021")

    # Single year – both forms should appear
    def test_single_year(self):
        # call the function for the single year 2020
        out = _generate_seasons_and_years(2020, 2020)

        # we expect two values: season "2020/2021" and the year "2020"
        assert out == ("2020/2021", "2020")

    # Inverted range – no seasons or years (empty tuple)
    def test_inverted_range_returns_empty(self):
        # if start year > end year, the range loop returns nothing
        out = _generate_seasons_and_years(2021, 2020)

        # we expect an empty tuple
        assert out == ()


"""
========================================================================================================================
get_competition_seasons
========================================================================================================================
"""


class TestGetCompetitionSeasons:
    # Checks that the function returns only seasons matching the year range and competition IDs.
    def test_filters_by_id_and_season_name(self, monkeypatch):
        # Prepare a list of sample competitions and seasons.
        competitions = [
            {"competition_id": 9, "season_id": 101, "season_name": "2019/2020"},
            {"competition_id": 16, "season_id": 202, "season_name": "2020"},
            {"competition_id": 999, "season_id": 303, "season_name": "2019/2020"},  # wrong competition_id
            {"competition_id": 9, "season_id": 404, "season_name": "2018/2019"},  # outside year range
        ]

        # Function replacing the data-fetching function. Returns the prepared list above.
        def fake_fetch():
            return competitions

        # Replace fetch_competitions with fake_fetch
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_manager.fetch_competitions",
            fake_fetch,
        )

        # Call the function with year range 2019–2020 and target IDs.
        result = get_competition_seasons(2019, 2020, target_comp_ids=[9, 16])

        # Expected result: only seasons (9,101) and (16,202).
        assert result == [(9, 101), (16, 202)]
        # Additional type check of returned values.
        assert all(isinstance(cid, int) and isinstance(sid, int) for cid, sid in result)

    # When there are no matching seasons, the function returns an empty list.
    def test_no_matches_returns_empty(self, monkeypatch):
        # Test data – all seasons are too old and out of range.
        competitions = [
            {"competition_id": 1, "season_id": 1, "season_name": "2010/2011"},
            {"competition_id": 2, "season_id": 2, "season_name": "2011"},
        ]

        # Function replacing the data-fetching function. Returns the prepared list above.
        def fake_fetch():
            return competitions

        # Replace fetch_competitions with fake_fetch
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_manager.fetch_competitions",
            fake_fetch,
        )

        # Call the function with year range 2019–2020 and target IDs.
        result = get_competition_seasons(2019, 2020, target_comp_ids=[9, 16])

        # No season matches, so the result should be [].
        assert result == []

    # When the year range is inverted (start > end), the result should be empty.
    def test_inverted_range_yields_empty(self, monkeypatch):
        # Test data – seasons would normally match, but the range is invalid.
        competitions = [
            {"competition_id": 9, "season_id": 10, "season_name": "2020/2021"},
            {"competition_id": 16, "season_id": 11, "season_name": "2020"},
        ]

        # Function replacing the data-fetching function.
        def fake_fetch():
            return competitions

        # Replace fetch_competitions with fake_fetch
        monkeypatch.setattr(
            "src.passes_per_minute.passes_counter.competition_manager.fetch_competitions",
            fake_fetch,
        )

        # Call the function with an inverted year range (2021–2020).
        result = get_competition_seasons(2021, 2020, target_comp_ids=[9, 16])

        # Range 2021–2020 is inverted, so the result should be [].
        assert result == []

    # When data fetching raises an error, the function should propagate the exception further.
    def test_fetch_error_propagates_from_public_api(self, monkeypatch):
        # Function replacing fetch that always raises ConnectionError.
        def raise_error():
            raise ConnectionError("raise_error")

        # Replace fetch_competitions with raise_error
        monkeypatch.setattr("src.passes_per_minute.passes_counter.competition_manager.fetch_competitions", raise_error)

        # Expect ConnectionError to be raised.
        with pytest.raises(ConnectionError):
            get_competition_seasons(2019, 2020, target_comp_ids=[9])
