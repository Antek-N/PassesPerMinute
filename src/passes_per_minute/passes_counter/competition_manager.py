import logging
from collections.abc import Sequence
from typing import Any

from passes_per_minute.passes_counter.http_client import get_json

log = logging.getLogger(__name__)


def _generate_seasons_and_years(start_year: int, end_year: int) -> tuple[str, ...]:
    """
    Generate season names in both "YYYY/YYYY+1" format and single-year "YYYY" format
    for a given range of years.

    :param start_year: The starting year of the range (inclusive).
    :param end_year: The ending year of the range (inclusive).
    :return: A tuple of strings representing valid season names and years.
    """
    # Generate season strings in "YYYY/YYYY+1" format
    seasons = [f"{year}/{year + 1}" for year in range(start_year, end_year + 1)]
    # Generate single-year strings in "YYYY" format
    years = [str(year) for year in range(start_year, end_year + 1)]

    return tuple(seasons + years)


def fetch_competitions() -> list[dict[str, Any]]:
    """
    Fetch the full list of available competitions from the StatsBomb open-data repository.

    :return: A list of dictionaries, each describing a competition with metadata
             such as competition_id, competition_name, season_id, and season_name.
    """
    url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
    log.info(f"Fetching competitions from {url}")  # Log start
    try:
        data = get_json(url)
        log.info(f"Fetched competitions ok: count={len(data)}")  # Log success
        return data
    except Exception:
        log.exception("Fetching competitions FAILED")  # Log failure
        raise


def get_competition_seasons(start_year: int, end_year: int, target_comp_ids: Sequence[int]) -> list[tuple[int, int]]:
    """
    Fetch the full list of competitions from the StatsBomb open-data repository
    and return only the (competition_id, season_id) pairs that match the given
    year range and competition IDs.

    :param start_year: The first year of the target range (inclusive).
    :param end_year: The last year of the target range (inclusive).
    :param target_comp_ids: A sequence of competition IDs to include in the filter.
    :return: A list of (competition_id, season_id) tuples for competitions
             that match the specified years and IDs.
    """
    # Log input params
    log.info(
        f"Filtering competitions start start_year={start_year} "
        f"end_year={end_year} target_ids={list(target_comp_ids)}"
    )

    # Generate all valid season names for the given range
    season_names = _generate_seasons_and_years(start_year, end_year)
    filtered = []  # List to store filtered competitions
    # Fetch all competitions from the source
    all_competitions = fetch_competitions()

    # Iterate over each competition and filter based on ID and season name
    for comp in all_competitions:
        if comp["competition_id"] in target_comp_ids and comp["season_name"] in season_names:
            # Store only competition_id and season_id in the results
            filtered.append((comp["competition_id"], comp["season_id"]))

    if not filtered:
        # Log no matches
        log.warning(
            f"No matching competitions for years=[{start_year}..{end_year}] " f"and ids={list(target_comp_ids)}"
        )
    else:
        # Log matches count
        log.info(f"Filtered competitions: matched={len(filtered)}")

    return filtered
