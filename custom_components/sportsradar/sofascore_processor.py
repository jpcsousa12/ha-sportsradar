"""Process SofaScore event data into SportsRadar format"""
import logging
from datetime import datetime, timezone
from typing import Any
import arrow

# Handle imports for both standalone testing and Home Assistant
try:
    from .sofascore_api import SofaScoreAPI
except ImportError:
    # Running standalone for testing
    import sofascore_api
    SofaScoreAPI = sofascore_api.SofaScoreAPI

_LOGGER = logging.getLogger(__name__)


def get_status_state(status_code: int, status_type: str) -> str:
    """Convert SofaScore status to state

    Args:
        status_code: SofaScore status code
        status_type: SofaScore status type

    Returns:
        State string: PRE, IN, POST, or NOT_FOUND

    The status *type* is the reliable discriminator - SofaScore uses many
    sport-specific numeric codes for periods (6/7 halves, 20 "Started",
    31 halftime, quarters, sets, innings...) and matching on a hand-written
    list of codes silently misclassifies anything not on it.
    """
    status_type = (status_type or "").lower()

    if status_type == "notstarted":
        return "PRE"
    if status_type in ("inprogress", "willstart", "interrupted", "suspended"):
        # Still an active fixture - keep tracking it closely.
        return "IN"
    if status_type in ("finished", "canceled", "cancelled", "postponed"):
        return "POST"

    # Unknown type: fall back to the documented code ranges.
    if status_code == 0:
        return "PRE"
    if status_code in (100, 110):
        return "POST"
    if status_code in (120, 130, 140):
        return "POST"
    if 0 < status_code < 100:
        return "IN"

    return "NOT_FOUND"


def get_period_name(status_code: int, status_type: str) -> str:
    """Get period/quarter name from status

    Args:
        status_code: SofaScore status code
        status_type: SofaScore status type

    Returns:
        Period name string
    """
    period_map = {
        0: "Not started",
        6: "1st half",
        7: "2nd half",
        31: "Halftime",
        41: "1st extra",
        42: "2nd extra",
        50: "Penalties",
        60: "Postponed",
        70: "Canceled",
        100: "Ended",
        110: "AET",
        120: "AP",
    }

    return period_map.get(status_code, f"Status {status_code}")


# Images are served from img.sofascore.com. The api.* hosts refuse most
# browsers (403), and the logos are loaded by the user's browser, not by HA.
IMG_BASE = "https://img.sofascore.com/api/v1"


def _team_logo(team: dict) -> str:
    return f"{IMG_BASE}/team/{team['id']}/image" if team.get("id") else ""


def _team_url(team: dict, sport: str) -> str:
    if team.get("id") and team.get("slug"):
        return f"https://www.sofascore.com/team/{sport}/{team['slug']}/{team['id']}"
    return ""


def _abbr(team: dict) -> str:
    # nameCode is the 3-letter code (POR, BEN); shortName is a full name
    return team.get("nameCode") or (team.get("name") or "")[:3].upper()


def _colors(team: dict) -> list[str]:
    c = team.get("teamColors") or {}
    return [c.get("primary", "#000000"), c.get("secondary", "#FFFFFF")]


def _live_clock(event: dict, status_code: int) -> str:
    """Match minute for football, e.g. "34'" or "45+2'".

    SofaScore gives the start of the current period and its offset ("initial",
    in seconds) instead of a running clock, so the minute is computed.
    """
    t = event.get("time") or {}
    start = t.get("currentPeriodStartTimestamp")
    if not start or status_code == 31:
        return ""
    initial = int(t.get("initial") or 0)
    max_s = int(t.get("max") or 0)
    now = datetime.now(timezone.utc).timestamp()
    minute = int((now - start + initial) // 60) + 1
    if minute < 1:
        return ""
    if max_s and minute > max_s // 60:
        return f"{max_s // 60}+{minute - max_s // 60}'"
    return f"{minute}'"


def _score(score: dict):
    value = score.get("current")
    if value is None:
        value = score.get("display")
    return value if value is not None else 0


async def async_process_sofascore_event(
    values: dict[str, Any],
    sensor_name: str,
    event: dict | None,
    team_id: int,
    api_client: SofaScoreAPI,
) -> dict[str, Any]:
    """Process a SofaScore event and populate values dict

    Args:
        values: Dictionary to populate with event data
        sensor_name: Name of the sensor (for logging)
        event: SofaScore event dictionary
        team_id: ID of the team we're tracking
        api_client: SofaScore API client for additional requests

    Returns:
        Updated values dictionary
    """
    if not event:
        values["api_message"] = "No upcoming event found for this team"
        values["state"] = "NOT_FOUND"
        _LOGGER.debug("%s: No event data provided", sensor_name)
        return values

    try:
        # Basic event info
        event_id = event.get("id")
        status = event.get("status", {})
        status_code = status.get("code", 0)
        status_type = status.get("type", "notstarted")

        # Determine state
        values["state"] = get_status_state(status_code, status_type)

        # Tournament/League info
        tournament = event.get("tournament", {})

        unique = tournament.get("uniqueTournament") or {}

        values["league"] = unique.get("name") or tournament.get("name", "")
        if unique.get("id"):
            values["league_logo"] = f"{IMG_BASE}/unique-tournament/{unique['id']}/image"
        elif tournament.get("id"):
            values["league_logo"] = f"{IMG_BASE}/tournament/{tournament['id']}/image"
        else:
            values["league_logo"] = ""

        # Sport lives under tournament.category; events have no top-level
        # "sport" key, so reading it there always gave "football".
        sport_name = (
            (tournament.get("category") or {}).get("sport", {}).get("slug")
            or (event.get("sport") or {}).get("slug")
            or values.get("sport")
            or "football"
        )
        values["sport"] = sport_name
        values["sport_path"] = sport_name

        # Season
        season = event.get("season", {})
        values["season"] = season.get("name", "") or season.get("year", "")

        # Teams
        home_team = event.get("homeTeam", {})
        away_team = event.get("awayTeam", {})

        # Determine which team is "our" team
        is_home = home_team.get("id") == team_id
        our_team = home_team if is_home else away_team
        opp_team = away_team if is_home else home_team

        # Team info
        values["team_id"] = str(our_team.get("id", ""))
        values["team_name"] = our_team.get("name", "")
        values["team_abbr"] = _abbr(our_team)
        values["team_long_name"] = our_team.get("fullName") or our_team.get("name", "")
        values["team_logo"] = _team_logo(our_team)
        values["team_url"] = _team_url(our_team, sport_name)
        values["team_homeaway"] = "home" if is_home else "away"
        values["team_colors"] = _colors(our_team)

        # Opponent info
        values["opponent_id"] = str(opp_team.get("id", ""))
        values["opponent_name"] = opp_team.get("name", "")
        values["opponent_abbr"] = _abbr(opp_team)
        values["opponent_long_name"] = opp_team.get("fullName") or opp_team.get("name", "")
        values["opponent_logo"] = _team_logo(opp_team)
        values["opponent_url"] = _team_url(opp_team, sport_name)
        values["opponent_homeaway"] = "away" if is_home else "home"
        values["opponent_colors"] = _colors(opp_team)

        values["event_name"] = event.get("name") or (
            f"{home_team.get('name', '')} - {away_team.get('name', '')}"
        )

        # Scores
        home_score = event.get("homeScore", {})
        away_score = event.get("awayScore", {})

        our_score, opp_score = (home_score, away_score) if is_home else (away_score, home_score)
        values["team_score"] = _score(our_score)
        values["opponent_score"] = _score(opp_score)

        # Event date/time
        start_timestamp = event.get("startTimestamp")
        if start_timestamp:
            event_date = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
            values["date"] = arrow.get(event_date).format("YYYY-MM-DDTHH:mm:ssZZ")

            # Calculate kickoff_in
            now = datetime.now(timezone.utc)
            delta = event_date - now
            total_seconds = int(delta.total_seconds())

            if total_seconds > 0:
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = (total_seconds % 3600) // 60

                if days > 0:
                    values["kickoff_in"] = f"in {days} day{'s' if days != 1 else ''}"
                elif hours > 0:
                    values["kickoff_in"] = f"in {hours} hour{'s' if hours != 1 else ''}"
                elif minutes > 0:
                    values["kickoff_in"] = f"in {minutes} minute{'s' if minutes != 1 else ''}"
                else:
                    values["kickoff_in"] = "Starting soon"
            else:
                values["kickoff_in"] = "Started"
        else:
            values["date"] = ""
            values["kickoff_in"] = ""

        # Venue
        venue = event.get("venue") or {}
        values["venue"] = venue.get("name") or (venue.get("stadium") or {}).get("name", "")
        venue_city = (venue.get("city") or {}).get("name", "")
        venue_country = (venue.get("country") or {}).get("name", "")
        if venue_city and venue_country:
            values["location"] = f"{venue_city}, {venue_country}"
        elif venue_city:
            values["location"] = venue_city
        else:
            values["location"] = venue_country or ""

        # Round info
        # quarter = current period. roundInfo.round is the matchday number
        # (7, 8...), which is not a period and showed up as "7" here.
        values["quarter"] = status.get("description") or get_period_name(status_code, status_type)

        # Clock: running minute while live, otherwise the status text
        values["clock"] = ""
        if values["state"] == "IN" and sport_name == "football":
            values["clock"] = _live_clock(event, status_code)
        if not values["clock"]:
            values["clock"] = status.get("description", "") or ""

        # Additional details for IN/POST states
        if values["state"] == "IN":
            values["private_fast_refresh"] = True
            # No win probability: SofaScore's event has none, and winnerCode
            # is only set once the match is over. The old 75/25 and 50/50
            # values were made up.

        elif values["state"] == "POST":
            # Determine winner
            winner_code = event.get("winnerCode", 0)
            if winner_code == 1:  # Home won
                values["team_winner"] = is_home
                values["opponent_winner"] = not is_home
            elif winner_code == 2:  # Away won
                values["team_winner"] = not is_home
                values["opponent_winner"] = is_home
            else:  # Draw
                values["team_winner"] = False
                values["opponent_winner"] = False

            values["private_fast_refresh"] = False

        elif values["state"] == "PRE":
            values["private_fast_refresh"] = False

            # Poll fast from 20 minutes before kickoff, and keep doing so
            # after the scheduled time while SofaScore still reports the game
            # as not started (late kickoff or a status that lags behind).
            # Without this the sensor falls back to the 10 minute rate right
            # at kickoff and stays on PRE well into the first half.
            if start_timestamp:
                now = datetime.now(timezone.utc)
                event_date = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
                delta = (event_date - now).total_seconds()
                if -3 * 3600 <= delta <= 1200:
                    values["private_fast_refresh"] = True

        # Event URL
        if event.get("slug") and event.get("customId"):
            values["event_url"] = (
                f"https://www.sofascore.com/{event['slug']}/{event['customId']}#id:{event_id}"
            )
        else:
            values["event_url"] = ""

        # TV network - SofaScore doesn't provide this in basic event data
        values["tv_network"] = ""

        # Series summary - for playoffs/series
        values["series_summary"] = ""

        # Records - not in basic event data
        values["team_record"] = ""
        values["opponent_record"] = ""
        values["team_rank"] = None
        values["opponent_rank"] = None

        # Odds - would need separate API call
        values["odds"] = ""
        values["overunder"] = ""

        # Possession, last play, etc. - need statistics API call
        values["possession"] = None
        values["last_play"] = ""
        values["down_distance_text"] = ""
        values["team_timeouts"] = None
        values["opponent_timeouts"] = None

        # Success message
        values["api_message"] = f"Event data retrieved successfully (Event ID: {event_id})"

        _LOGGER.debug(
            "%s: Processed SofaScore event %s - %s vs %s (%s)",
            sensor_name,
            event_id,
            values["team_name"],
            values["opponent_name"],
            values["state"],
        )

    except Exception as error:  # pylint: disable=broad-exception-caught
        # A malformed or unexpected payload should show NOT_FOUND on the
        # sensor, not raise through the coordinator.
        _LOGGER.error("%s: Error processing SofaScore event: %s", sensor_name, error)
        _LOGGER.exception("Full traceback:")
        values["api_message"] = f"Error processing event data: {str(error)}"
        values["state"] = "NOT_FOUND"

    return values


async def async_get_sofascore_statistics(
    values: dict[str, Any],
    event_id: int,
    team_id: int,
    api_client: SofaScoreAPI,
    sensor_name: str,
) -> dict[str, Any]:
    """Fetch an event's statistics and add them to values.

    Args:
        values: Dictionary to update with statistics
        event_id: SofaScore event ID
        team_id: ID of the team we're tracking
        api_client: SofaScore API client
        sensor_name: Name of the sensor (for logging)

    Returns:
        Updated values dictionary
    """
    try:
        stats_data = await api_client.get_event_statistics(event_id)
    except Exception as error:  # pylint: disable=broad-exception-caught
        # Statistics are optional garnish; never let them fail an update.
        _LOGGER.debug("%s: Could not fetch statistics: %s", sensor_name, error)
        return values

    apply_statistics(values, stats_data, sensor_name)
    _LOGGER.debug("%s: Added statistics for event %s", sensor_name, event_id)
    return values


def apply_statistics(
    values: dict[str, Any], stats_data: dict | None, sensor_name: str = ""
) -> dict[str, Any]:
    """Add shots, corners, cards, xG and possession from /event/{id}/statistics."""
    if not stats_data:
        return values

    try:
        _apply_statistics(values, stats_data)
    except Exception as error:  # pylint: disable=broad-exception-caught
        # An unexpected payload shape must not fail the update.
        _LOGGER.debug("%s: Could not read statistics: %s", sensor_name, error)

    return values


def _apply_statistics(values: dict[str, Any], stats_data: dict) -> None:
    statistics = stats_data.get("statistics", [])

    # SofaScore returns one block per period: "ALL" (match totals), then
    # "1ST", "2ND" and so on. Only the "ALL" block is wanted - iterating
    # over every block lets the last one win, which silently replaces the
    # match totals with second-half-only numbers once a game gets that far.
    period_stats = next(
        (p for p in statistics if p.get("period") == "ALL"),
        statistics[0] if statistics else None,
    )

    if not period_stats:
        return

    # Find home/away stats
    home_stats = {}
    away_stats = {}

    for group in period_stats.get("groups", []):
        for item in group.get("statisticsItems", []):
            # homeValue/awayValue are numbers; home/away are display
            # strings ("5", "54%"). Stored under both key and name.
            home = item.get("homeValue", item.get("home", ""))
            away = item.get("awayValue", item.get("away", ""))
            for label in (item.get("key"), item.get("name")):
                if label and label not in home_stats:
                    home_stats[label] = home
                    away_stats[label] = away

    # Determine if we're home or away
    is_home = values.get("team_homeaway") == "home"
    our_stats = home_stats if is_home else away_stats
    opp_stats = away_stats if is_home else home_stats

    # Only football statistics are mapped to attributes.
    if values.get("sport") not in ["football", "soccer"]:
        return

    # Keyed by the stable "key" field; "name" is display text
    for attr, key, name in (
        ("shots_on_target", "shotsOnGoal", "Shots on target"),
        ("total_shots", "totalShotsOnGoal", "Total shots"),
        ("corners", "cornerKicks", "Corner kicks"),
        ("yellow_cards", "yellowCards", "Yellow cards"),
        ("red_cards", "redCards", "Red cards"),
        ("xg", "expectedGoals", "Expected goals"),
    ):
        for prefix, stats in (("team", our_stats), ("opponent", opp_stats)):
            value = stats.get(key, stats.get(name))
            if value in (None, "") and attr in ("yellow_cards", "red_cards"):
                value = 0  # SofaScore omits card rows until there is one
            values[f"{prefix}_{attr}"] = value

    # Ball possession already includes the percent sign ("64%")
    possession = our_stats.get("ballPossession", our_stats.get("Ball possession"))
    if possession not in (None, ""):
        possession = str(possession).strip()
        if possession.endswith(".0"):
            possession = possession[:-2]
        values["possession"] = (
            possession if possession.endswith("%") else f"{possession}%"
        )


def _hex(color: str | None) -> str | None:
    if not color:
        return None
    return color if color.startswith("#") else f"#{color}"


def apply_lineups(values: dict[str, Any], lineups: dict | None) -> dict[str, Any]:
    """Kit colours and formation for this match, from /event/{id}/lineups.

    playerColor/goalkeeperColor are the shirts actually worn in this game
    (away kits included), unlike team_colors, which are the club colours.
    Published with the line-ups, about an hour before kickoff.
    """
    if not lineups:
        return values
    is_home = values.get("team_homeaway") == "home"
    sides = {
        "team": lineups.get("home" if is_home else "away") or {},
        "opponent": lineups.get("away" if is_home else "home") or {},
    }
    for prefix, side in sides.items():
        kit = side.get("playerColor") or {}
        gk = side.get("goalkeeperColor") or {}
        if kit.get("primary"):
            values[f"{prefix}_kit_colors"] = [
                _hex(kit.get("primary")), _hex(kit.get("number")), _hex(kit.get("outline"))
            ]
        if gk.get("primary"):
            values[f"{prefix}_goalkeeper_colors"] = [
                _hex(gk.get("primary")), _hex(gk.get("number")), _hex(gk.get("outline"))
            ]
        if side.get("formation"):
            values[f"{prefix}_formation"] = side["formation"]
    return values


def _minute(incident: dict) -> str:
    minute = incident.get("time")
    if minute is None:
        return ""
    added = incident.get("addedTime")
    if added and added != 999:
        return f"{minute}+{added}'"
    return f"{minute}'"


def describe_incident(incident: dict, home_name: str, away_name: str) -> str | None:
    """One line for the most recent incident, or None to skip it."""
    kind = incident.get("incidentType")
    cls = incident.get("incidentClass") or ""
    team = home_name if incident.get("isHome") else away_name
    minute = _minute(incident)
    player = incident.get("playerName") or (incident.get("player") or {}).get("name", "")

    if kind == "goal":
        score = f"{incident.get('homeScore', '')}-{incident.get('awayScore', '')}"
        if cls == "ownGoal":
            return f"{minute} Goal for {team}: own goal by {player} ({score})"
        label = "Penalty goal" if cls == "penalty" else "Goal"
        return f"{minute} {label}: {player} ({team}) {score}"
    if kind == "card":
        label = {"yellow": "Yellow card", "red": "Red card", "yellowRed": "Second yellow"}.get(cls, "Card")
        return f"{minute} {label}: {player} ({team})"
    if kind == "substitution":
        pin = (incident.get("playerIn") or {}).get("name", "")
        pout = (incident.get("playerOut") or {}).get("name", "")
        return f"{minute} Substitution ({team}): {pin} on, {pout} off"
    if kind == "varDecision":
        return f"{minute} VAR ({team}): {cls}"
    if kind == "inGamePenalty":
        return f"{minute} Penalty {cls} ({team})"
    return None  # period markers, injury time announcements


def apply_incidents(values: dict[str, Any], incidents: dict | None, home_name: str, away_name: str) -> dict[str, Any]:
    """last_play = newest goal/card/substitution/VAR incident."""
    if not incidents:
        return values
    for incident in incidents.get("incidents") or []:
        text = describe_incident(incident, home_name, away_name)
        if text:
            values["last_play"] = text
            break
    return values
