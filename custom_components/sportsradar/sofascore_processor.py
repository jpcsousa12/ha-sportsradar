"""Process SofaScore event data into SportsRadar format"""
import logging
from datetime import datetime, timezone
from typing import Any
import arrow

# Handle imports for both standalone testing and Home Assistant
try:
    from .const import DEFAULT_LOGO
    from .sofascore_api import SofaScoreAPI
except ImportError:
    # Running standalone for testing - use test constants
    try:
        from test_const import DEFAULT_LOGO
    except ImportError:
        # Fallback to hardcoded values
        DEFAULT_LOGO = "https://cdn0.iconfinder.com/data/icons/shift-interfaces/32/Error-512.png"
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
        0: "Scheduled",
        6: "1st Half",
        7: "Halftime",
        31: "2nd Half",
        41: "1st Quarter",
        42: "2nd Quarter",
        43: "3rd Quarter",
        44: "4th Quarter",
        100: "Final",
        110: "Awarded",
        120: "Postponed",
        130: "Cancelled",
    }

    return period_map.get(status_code, f"Status {status_code}")


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

        values["league"] = tournament.get("name", "Unknown League")
        values["league_logo"] = f"https://api.sofascore.com/api/v1/unique-tournament/{tournament.get('uniqueTournament', {}).get('id')}/image" if tournament.get("uniqueTournament") else DEFAULT_LOGO
        values["event_name"] = event.get("name", "")

        # Sport info
        sport_name = event.get("sport", {}).get("name", "football").lower()
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
        values["team_abbr"] = our_team.get("shortName", our_team.get("name", "")[:3].upper())
        values["team_long_name"] = our_team.get("name", "")
        values["team_logo"] = f"https://api.sofascore.com/api/v1/team/{our_team.get('id')}/image" if our_team.get("id") else DEFAULT_LOGO
        values["team_homeaway"] = "home" if is_home else "away"

        # Team colors
        team_colors = our_team.get("teamColors", {})
        values["team_colors"] = [
            team_colors.get("primary", "#000000"),
            team_colors.get("secondary", "#FFFFFF"),
            team_colors.get("text", "#FFFFFF"),
        ]

        # Opponent info
        values["opponent_id"] = str(opp_team.get("id", ""))
        values["opponent_name"] = opp_team.get("name", "")
        values["opponent_abbr"] = opp_team.get("shortName", opp_team.get("name", "")[:3].upper())
        values["opponent_long_name"] = opp_team.get("name", "")
        values["opponent_logo"] = f"https://api.sofascore.com/api/v1/team/{opp_team.get('id')}/image" if opp_team.get("id") else DEFAULT_LOGO
        values["opponent_homeaway"] = "away" if is_home else "home"

        # Opponent colors
        opp_colors = opp_team.get("teamColors", {})
        values["opponent_colors"] = [
            opp_colors.get("primary", "#000000"),
            opp_colors.get("secondary", "#FFFFFF"),
            opp_colors.get("text", "#FFFFFF"),
        ]

        # Scores
        home_score = event.get("homeScore", {})
        away_score = event.get("awayScore", {})

        if is_home:
            values["team_score"] = home_score.get("current", 0) or home_score.get("display", 0) or 0
            values["opponent_score"] = away_score.get("current", 0) or away_score.get("display", 0) or 0
        else:
            values["team_score"] = away_score.get("current", 0) or away_score.get("display", 0) or 0
            values["opponent_score"] = home_score.get("current", 0) or home_score.get("display", 0) or 0

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
        venue = event.get("venue", {})
        values["venue"] = venue.get("stadium", {}).get("name", "")
        venue_city = venue.get("city", {}).get("name", "")
        venue_country = venue.get("country", {}).get("name", "")
        if venue_city and venue_country:
            values["location"] = f"{venue_city}, {venue_country}"
        elif venue_city:
            values["location"] = venue_city
        else:
            values["location"] = venue_country or ""

        # Round info
        round_info = event.get("roundInfo", {})
        values["quarter"] = round_info.get("round", "") or get_period_name(status_code, status_type)

        # Time/Clock
        values["clock"] = status.get("description", "") or ""

        # Additional details for IN/POST states
        if values["state"] == "IN":
            values["private_fast_refresh"] = True

            # Win probability (if available)
            win_prob = event.get("winnerCode")
            if win_prob == 1:  # Home winning
                if is_home:
                    values["team_win_probability"] = 75.0
                    values["opponent_win_probability"] = 25.0
                else:
                    values["team_win_probability"] = 25.0
                    values["opponent_win_probability"] = 75.0
            elif win_prob == 2:  # Away winning
                if is_home:
                    values["team_win_probability"] = 25.0
                    values["opponent_win_probability"] = 75.0
                else:
                    values["team_win_probability"] = 75.0
                    values["opponent_win_probability"] = 25.0
            else:
                values["team_win_probability"] = 50.0
                values["opponent_win_probability"] = 50.0

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

            # Check if game is within 20 minutes
            if start_timestamp:
                now = datetime.now(timezone.utc)
                event_date = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
                delta = event_date - now
                if 0 <= delta.total_seconds() <= 1200:  # Within 20 minutes
                    values["private_fast_refresh"] = True

        # Event URL
        if event.get("slug"):
            home_slug = event.get("homeTeam", {}).get("slug", "")
            away_slug = event.get("awayTeam", {}).get("slug", "")
            custom_id = event.get("customId", "")
            values["event_url"] = f"https://www.sofascore.com/{home_slug}-{away_slug}/{custom_id}"
        else:
            values["event_url"] = ""

        # TV network - SofaScore doesn't provide this in basic event data
        values["tv_network"] = ""

        # Series summary - for playoffs/series
        values["series_summary"] = ""

        # Records - not in basic event data
        values["team_record"] = ""
        values["opponent_record"] = ""
        values["team_rank"] = 0
        values["opponent_rank"] = 0

        # Odds - would need separate API call
        values["odds"] = ""
        values["overunder"] = ""

        # Possession, last play, etc. - need statistics API call
        values["possession"] = ""
        values["last_play"] = ""
        values["down_distance_text"] = ""
        values["team_timeouts"] = 0
        values["opponent_timeouts"] = 0

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
    """Fetch and add statistics to values dict

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

        if not stats_data:
            return values

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
            return values

        # Find home/away stats
        home_stats = {}
        away_stats = {}

        for group in period_stats.get("groups", []):
            for item in group.get("statisticsItems", []):
                stat_name = item.get("name", "")
                home_stats[stat_name] = item.get("home", "")
                away_stats[stat_name] = item.get("away", "")

        # Determine if we're home or away
        is_home = values.get("team_homeaway") == "home"
        our_stats = home_stats if is_home else away_stats
        opp_stats = away_stats if is_home else home_stats

        # Map statistics to values
        # For football/soccer
        if values.get("sport") in ["football", "soccer"]:
            values["team_shots_on_target"] = our_stats.get("Shots on target", 0)
            values["opponent_shots_on_target"] = opp_stats.get("Shots on target", 0)
            values["team_total_shots"] = our_stats.get("Total shots", 0)
            values["opponent_total_shots"] = opp_stats.get("Total shots", 0)

            # Ball possession already includes the percent sign ("64%")
            possession = our_stats.get("Ball possession")
            if possession:
                possession = str(possession).strip()
                values["possession"] = (
                    possession if possession.endswith("%") else f"{possession}%"
                )

        _LOGGER.debug("%s: Added statistics for event %s", sensor_name, event_id)

    except Exception as error:  # pylint: disable=broad-exception-caught
        # Statistics are optional garnish; never let them fail an update.
        _LOGGER.debug("%s: Could not fetch statistics: %s", sensor_name, error)

    return values
