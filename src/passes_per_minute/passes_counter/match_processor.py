import logging
from collections import defaultdict
from threading import Lock
from typing import Any

from passes_per_minute.passes_counter.http_client import get_json

log = logging.getLogger(__name__)


class MatchProcessor:
    """
    Class responsible for:
      - processing individual matches,
      - counting positional statistics (minutes, passes),
      - counting the number of processed matches.
    """

    def __init__(self) -> None:
        self._match_counter = 0
        self._counter_lock = Lock()  # lock to protect counter in multithreaded environment

    @staticmethod
    def _extract_starting_xi(event: dict[str, Any], player_positions: dict[int, list[dict[str, Any]]]) -> None:
        """
        Extract the starting eleven players from the "Starting XI" event
        and initialize their position intervals.

        :param event: A match event containing lineup information.
        :param player_positions: A mapping from player IDs to their list of position intervals.
        :return: None. Updates player_positions in place.
        """
        for player in event["tactics"]["lineup"]:
            player_id = player["player"]["id"]  # player ID
            position = player["position"]["name"]  # position from lineup

            # create a list of intervals (here initially one open interval of play)
            player_positions[player_id] = [{"position": position, "start_time": 0, "end_time": None}]

    @staticmethod
    def _handle_substitution(event: dict[str, Any], player_positions: dict[int, list[dict[str, Any]]]) -> None:
        """
        Handle substitution events by closing the outgoing player's interval
        and opening a new interval for the incoming player in the same position.

        :param event: A substitution event dictionary.
        :param player_positions: A mapping from player IDs to their list of position intervals.
        :return: None. Updates player_positions in place.
        """
        player_out = event["player"]["id"]  # ID of the player leaving the field
        player_in = event["substitution"]["replacement"]["id"]  # ID of the player coming in
        minute = event["minute"]  # substitution minute

        # safeguard – if the substituted player was not previously registered
        if player_out not in player_positions:
            log.warning(f"Substitution ignored: player_out={player_out} not tracked at minute={minute}")  # Log warning
            return

        # take the position of the player who was substituted
        position = player_positions[player_out][-1]["position"]
        # close his interval
        player_positions[player_out][-1]["end_time"] = minute
        # open an interval for the incoming player
        player_positions[player_in] = [{"position": position, "start_time": minute, "end_time": None}]

    @staticmethod
    def _update_player_positions(event: dict[str, Any], player_positions: dict[int, list[dict[str, Any]]]) -> None:
        """
        Update a player's position when an event indicates a positional change
        without substitution.

        :param event: An event potentially containing a "position" change for a player.
        :param player_positions: A mapping from player IDs to their list of position intervals.
        :return: None. Updates player_positions in place.
        """
        player_id = event["player"]["id"]  # player ID

        # check if the event contains position info
        position_obj = event.get("position")
        if not position_obj:
            return

        position = position_obj["name"]  # new position from the event
        minute = event["minute"]  # event minute

        if player_id in player_positions:
            current_position = player_positions[player_id][-1]["position"]
            # if the player actually changed position
            if position != current_position:
                # close previous interval
                player_positions[player_id][-1]["end_time"] = minute
                # add a new interval with the new position
                player_positions[player_id].append({"position": position, "start_time": minute, "end_time": None})

    @staticmethod
    def _finalize_process(
        player_positions: dict[int, list[dict[str, Any]]],
        match_positions: defaultdict[str, dict[str, int]],
        events: list[dict[str, Any]],
    ) -> None:
        """
        Finalize processing by closing open intervals and summing played minutes
        for all players by position.

        :param player_positions: Mapping of player IDs to their position intervals.
        :param match_positions: Dictionary accumulating total minutes and passes by position.
        :param events: List of all match events, used to determine match end time.
        :return: None. Updates match_positions in place.
        """
        # determine last minute of the match (from events or default 90)
        if events:
            minutes = [event.get("minute", 0) for event in events]
            match_end_time = max(minutes) if minutes else 90
        else:
            match_end_time = 90

        # - close intervals and sum played minutes -
        # iterate through all players
        for _, positions_list in player_positions.items():
            # if the last interval is still open, close it at match end
            if positions_list and positions_list[-1]["end_time"] is None:
                positions_list[-1]["end_time"] = match_end_time

            # sum minutes from each interval
            for position_entry in positions_list:
                position = position_entry["position"]
                minutes_played = position_entry["end_time"] - position_entry["start_time"]

                if minutes_played < 0:
                    minutes_played = 0  # safeguard against invalid data

                match_positions[position]["minutes"] += minutes_played

    @staticmethod
    def _aggregate_pass_data(
        events: list[dict[str, Any]],
        match_positions: defaultdict[str, dict[str, int]],
        player_positions: dict[int, list[dict[str, Any]]],
    ) -> None:
        """
        Aggregate pass statistics by assigning passes to player positions
        at the time they were made.

        :param events: A list of match events.
        :param match_positions: Dictionary accumulating total minutes and passes by position.
        :param player_positions: Mapping of player IDs to their position intervals.
        :return: None. Updates match_positions in place.
        """
        # iterate through all events
        for event in events:
            # take only passes with an assigned player
            if event.get("type", {}).get("name") == "Pass" and "player" in event:
                player_id = event["player"]["id"]
                minute = event.get("minute", 0)

                # check if player is being tracked in player_positions
                if player_id in player_positions:
                    # check what position he was in at the moment of the pass
                    for position_entry in player_positions[player_id]:
                        start_t = position_entry["start_time"]
                        end_t = position_entry["end_time"]

                        if end_t is None:
                            continue  # open interval, will be closed later in _finalize_process

                        # if the pass minute is within the interval
                        if start_t <= minute < end_t:
                            current_position = position_entry["position"]
                            match_positions[current_position]["passes"] += 1
                            break  # pass assigned, no need to check further intervals

    def get_match_counter(self) -> int:
        """
        Retrieve the number of matches processed so far.

        :return: An integer representing the total number of processed matches.
        """
        with self._counter_lock:
            return self._match_counter

    def process_match(self, match_id: int | str) -> defaultdict[str, dict[str, int]]:
        """
        Process a single match by analyzing events, calculating positional minutes
        and passes, and updating the internal match counter.

        :param match_id: The unique identifier of the match (integer or string).
        :return: A defaultdict where each position maps to a dictionary
                 with keys "passes" and "minutes".
        """
        log.info(f"Process match start match_id={match_id}")  # Log start

        # results dictionary: {position: {"passes": X, "minutes": Y}}
        match_positions: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"passes": 0, "minutes": 0})

        # map players to a list of their position intervals
        player_positions: dict[int, list[dict[str, Any]]] = {}

        # fetch all match events from StatsBomb API
        events = get_json(f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json")
        log.info(f"Events loaded match_id={match_id} count={len(events)}")  # Log success

        # iterate through all match events
        for event in events:
            event_type = event.get("type", {}).get("name")

            # initialize starting eleven
            if event_type == "Starting XI":
                self._extract_starting_xi(event, player_positions)
            # handle substitutions
            elif event_type == "Substitution":
                self._handle_substitution(event, player_positions)

            # update position during play (without personnel changes)
            if "player" in event:
                self._update_player_positions(event, player_positions)

        if not player_positions:
            log.warning(f"No Starting XI found match_id={match_id}")  # Log missing lineup

        # close open intervals and count minutes
        self._finalize_process(player_positions, match_positions, events)
        # sum passes by position
        self._aggregate_pass_data(events, match_positions, player_positions)

        # increment processed match counter
        with self._counter_lock:
            self._match_counter += 1
            log.info(f"Processed match counter={self._match_counter} match_id={match_id}")  # Log progress

            # Log result
            total_minutes = sum(value["minutes"] for value in match_positions.values())
            total_passes = sum(value["passes"] for value in match_positions.values())
            log.info(
                f"Match processed match_id={match_id} positions={len(match_positions)} "
                f"minutes_total={total_minutes} passes_total={total_passes}"
            )

        return match_positions
