import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from passes_per_minute.passes_counter.http_client import get_json
from passes_per_minute.passes_counter.match_processor import MatchProcessor

log = logging.getLogger(__name__)

MATCH_PROCESSOR = MatchProcessor()
MAX_WORKERS = 12
MAX_MATCH_RETRIES = 3


def _empty_stats() -> defaultdict[str, dict[str, int]]:
    """
    Create an empty statistics container for player positions.

    :return: A defaultdict where each position maps to a dictionary
             with keys "passes" and "minutes", both initialized to 0.
    """
    return defaultdict(lambda: {"passes": 0, "minutes": 0})


def _fetch_matches(competition_id: int, season_id: int) -> list[dict[str, Any]]:
    """
    Fetch the list of matches for a given competition and season.

    :param competition_id: The unique identifier of the competition (e.g., league).
    :param season_id: The unique identifier of the season within the competition.
    :return: A list of match dictionaries retrieved from the StatsBomb open-data repository.
    """
    url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/{competition_id}/{season_id}.json"
    log.info(f"Fetching matches from {url}")  # Log start
    try:
        matches = get_json(url)
        log.info(f"Fetched matches ok: count={len(matches)}")  # Log success
        return matches
    except Exception:
        log.exception("Fetching matches FAILED")  # Log failure
        raise


def _extract_match_ids(matches: Sequence[Mapping[str, Any]]) -> list[int]:
    """
    Extract the match IDs from the list of match dictionaries.

    :param matches: A sequence of match dictionaries containing metadata.
    :return: A list of match IDs as integers.
    """
    return [match["match_id"] for match in matches]


def _submit_all_tasks(executor: ThreadPoolExecutor, match_ids: Sequence[int]) -> dict[Future, int]:
    """
    Submit tasks to process all matches concurrently.

    :param executor: A ThreadPoolExecutor to run tasks in parallel.
    :param match_ids: A sequence of match identifiers to process.
    :return: A dictionary mapping Future objects to their associated match IDs.
    """
    futures = {}
    for match_id in match_ids:
        # Pass the match identifier to the process_match function
        futures[executor.submit(MATCH_PROCESSOR.process_match, match_id)] = match_id
    log.info(f"Submitted tasks: total={len(futures)}")  # Log tasks count
    return futures


def _aggregate_positions(
    total: defaultdict[str, dict[str, int]],
    partial: Mapping[str, Mapping[str, int]],
) -> None:
    """
    Aggregate partial position statistics into the total statistics.

    :param total: The running totals of passes and minutes grouped by position.
    :param partial: The partial statistics from a single match, grouped by position.
    :return: None. Updates the `total` dictionary in place.
    """
    for position, stats in partial.items():
        total[position]["passes"] += stats["passes"]
        total[position]["minutes"] += stats["minutes"]


def _handle_error_or_retry(
    executor: ThreadPoolExecutor,
    futures: dict[Future, int],
    attempts: defaultdict[int, int],
    match_id: int,
    exception: Exception,
) -> None:
    """
    Handle an error during match processing, retrying if the maximum retries
    have not been exceeded.

    :param executor: A ThreadPoolExecutor to resubmit failed tasks if needed.
    :param futures: The current mapping of Futures to match IDs.
    :param attempts: A counter tracking the number of retries per match ID.
    :param match_id: The ID of the match that failed.
    :param exception: The exception raised during match processing.
    :return: None. May re-submit the match for processing or raise an error if retries are exhausted.
    """
    log.warning(f"Error processing match {match_id}: {exception}")  # Log error

    if attempts[match_id] < MAX_MATCH_RETRIES:
        attempts[match_id] += 1
        log.info(f"Retrying match {match_id}, attempt {attempts[match_id]}")  # Log retry
        new_future = executor.submit(MATCH_PROCESSOR.process_match, match_id)
        futures[new_future] = match_id
    else:
        log.error(f"Match {match_id} failed after {MAX_MATCH_RETRIES} attempts")  # Log failure
        raise RuntimeError(f"Failed to process match {match_id} after {MAX_MATCH_RETRIES} retries") from exception


def _drain_results_loop(
    executor: ThreadPoolExecutor,
    futures: dict[Future, int],
    competition_positions: defaultdict[str, dict[str, int]],
) -> None:
    """
    Process results of completed tasks, aggregating statistics or retrying on failure.

    :param executor: A ThreadPoolExecutor for resubmitting failed tasks.
    :param futures: A mapping of Futures to their corresponding match IDs.
    :param competition_positions: The aggregated statistics container for the competition.
    :return: None. Updates competition_positions in place.
    """
    attempts: defaultdict[int, int] = defaultdict(int)
    log.info(f"Draining results: pending={len(futures)}")  # Log start

    while futures:
        for future in as_completed(list(futures.keys())):
            match_id = futures.pop(future)
            try:
                match_positions = future.result()
                _aggregate_positions(competition_positions, match_positions)

            except (ValueError, KeyError, TypeError) as e:
                _handle_error_or_retry(executor, futures, attempts, match_id, e)

            except ConnectionError as e:
                _handle_error_or_retry(executor, futures, attempts, match_id, e)

            except Exception:
                log.exception(f"Unexpected error during processing match {match_id}")  # Log unexpected
                raise

    log.info("Draining results complete")  # Log success


def get_match_counter() -> int:
    """
    Retrieve the number of matches that have been processed so far.

    :return: An integer representing the total count of processed matches.
    """
    return MATCH_PROCESSOR.get_match_counter()


def process_competition(competition_id: int, season_id: int) -> defaultdict[str, dict[str, int]]:
    """
    Process all matches of a given competition and season, aggregating statistics by player position.

    :param competition_id: The unique identifier of the competition.
    :param season_id: The unique identifier of the season.
    :return: A defaultdict with player positions as keys and aggregated
             statistics {"passes": int, "minutes": int} as values.
    """
    competition_positions = _empty_stats()
    matches = _fetch_matches(competition_id, season_id)
    match_ids = _extract_match_ids(matches)
    log.info(f"Matches to process: count={len(match_ids)}")  # Log input size

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        log.info(f"Thread pool created max_workers={MAX_WORKERS}")  # Log start
        futures = _submit_all_tasks(executor, match_ids)
        _drain_results_loop(executor, futures, competition_positions)

    log.info(f"Process competition complete positions={len(competition_positions)}")  # Log result
    return competition_positions
