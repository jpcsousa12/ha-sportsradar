"""SofaScore API Client for SportsRadar"""
import logging
from typing import Any
import aiohttp
import asyncio

_LOGGER = logging.getLogger(__name__)

# Number of attempts for transient failures (429 / 5xx / network errors)
MAX_ATTEMPTS = 3
# Base seconds for exponential backoff between attempts
BACKOFF_BASE = 1.5


class SofaScoreApiError(Exception):
    """Raised when SofaScore cannot be reached or refuses the request.

    A missing resource (HTTP 404) is NOT an error - that is reported as None,
    because "this team has no upcoming match" is a normal answer.
    """

# SofaScore API Base URL
SOFASCORE_API_BASE = "https://api.sofascore.com/api/v1"

# Headers to mimic a normal browser request and avoid 403 errors
SOFASCORE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# Sport mapping - SofaScore sport IDs
SPORT_MAP = {
    "football": 1,  # Soccer
    "basketball": 2,
    "tennis": 5,
    "cricket": 3,
    "hockey": 4,  # Ice hockey
    "american-football": 12,
    "baseball": 9,
    "volleyball": 23,
    "handball": 6,
    "rugby": 12,
    "mma": 20,
    "motorsport": 19,
}


class SofaScoreAPI:
    """Class to interact with SofaScore unofficial API"""

    def __init__(self, timeout: int = 30):
        """Initialize the SofaScore API client

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=SOFASCORE_HEADERS)
        return self.session

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _make_request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a request to SofaScore API

        Args:
            endpoint: API endpoint (without base URL)
            params: Optional query parameters

        Returns:
            JSON response as dict, or None if the resource does not exist (404)

        Raises:
            SofaScoreApiError: on 403, 429, 5xx, timeouts or network errors, so
                the caller can mark the sensor unavailable instead of silently
                reporting "no game".
        """
        url = f"{SOFASCORE_API_BASE}{endpoint}"
        last_error = "unknown error"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                session = await self._get_session()
                async with session.get(url, params=params, timeout=self.timeout) as response:
                    if response.status == 200:
                        return await response.json()

                    if response.status == 404:
                        # Normal "nothing here" answer - not an error.
                        _LOGGER.debug("SofaScore API returned 404 for %s", url)
                        return None

                    if response.status == 403:
                        # Blocked at the edge. Retrying with identical headers
                        # will not help, so fail fast and surface it.
                        raise SofaScoreApiError(
                            f"SofaScore refused the request (403 Forbidden) for {endpoint}. "
                            "The API is blocking this client - headers may need updating."
                        )

                    if response.status == 429 or response.status >= 500:
                        last_error = f"HTTP {response.status}"
                        retry_after = response.headers.get("Retry-After")
                        delay = BACKOFF_BASE * (2 ** (attempt - 1))
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                    else:
                        raise SofaScoreApiError(
                            f"SofaScore returned HTTP {response.status} for {endpoint}"
                        )

            except asyncio.TimeoutError:
                last_error = "timeout"
                delay = BACKOFF_BASE * (2 ** (attempt - 1))
            except aiohttp.ClientError as error:
                last_error = f"network error: {error}"
                delay = BACKOFF_BASE * (2 ** (attempt - 1))

            if attempt < MAX_ATTEMPTS:
                _LOGGER.debug(
                    "SofaScore request to %s failed (%s), retrying in %.1fs (attempt %d/%d)",
                    url, last_error, delay, attempt, MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)

        raise SofaScoreApiError(
            f"SofaScore request to {endpoint} failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )

    async def search_teams(self, query: str) -> list[dict[str, Any]]:
        """Search for teams by name

        Args:
            query: Team name to search for

        Returns:
            list of team dictionaries with id, name, slug, sport, etc.
        """
        endpoint = "/search/all"
        params = {"q": query}

        data = await self._make_request(endpoint, params)

        if not data:
            _LOGGER.debug("No search results for query: %s", query)
            return []

        teams = []

        # SofaScore returns results as a flat list with type and entity fields
        for result in data.get("results", []):
            if result.get("type") == "team":
                entity = result.get("entity", {})
                teams.append({
                    "id": entity.get("id"),
                    "name": entity.get("name"),
                    "slug": entity.get("slug"),
                    "sport": entity.get("sport", {}).get("name"),
                    "sport_id": entity.get("sport", {}).get("id"),
                    "country": entity.get("country", {}).get("name", ""),
                    "team_colors": {
                        "primary": entity.get("teamColors", {}).get("primary", "#000000"),
                        "secondary": entity.get("teamColors", {}).get("secondary", "#FFFFFF"),
                    },
                    "logo": f"https://api.sofascore.com/api/v1/team/{entity.get('id')}/image" if entity.get('id') else None,
                })

        _LOGGER.debug("Found %d teams for query '%s'", len(teams), query)
        return teams

    async def get_team_next_event(self, team_id: int, page: int = 0) -> dict | None:
        """Get next upcoming event for a team

        Args:
            team_id: SofaScore team ID
            page: Page number (default 0 for next event)

        Returns:
            Event data dictionary or None if no upcoming event
        """
        endpoint = f"/team/{team_id}/events/next/{page}"

        data = await self._make_request(endpoint)

        if not data:
            _LOGGER.debug("No next event found for team_id: %s", team_id)
            return None

        # Return first event if available
        events = data.get("events", [])
        if events:
            return events[0]

        return None

    async def get_team_last_event(self, team_id: int, page: int = 0) -> dict | None:
        """Get last completed event for a team

        Args:
            team_id: SofaScore team ID
            page: Page number (default 0 for most recent)

        Returns:
            Event data dictionary or None if no previous event
        """
        endpoint = f"/team/{team_id}/events/last/{page}"

        data = await self._make_request(endpoint)

        if not data:
            _LOGGER.debug("No last event found for team_id: %s", team_id)
            return None

        # This endpoint returns events oldest-first, so the most recent match
        # is the LAST element. A match that is currently in progress also
        # appears here at the tail, which is how a restart mid-match recovers.
        events = data.get("events", [])
        if events:
            return events[-1]

        return None

    async def get_event_details(self, event_id: int) -> dict | None:
        """Get detailed information about a specific event

        Args:
            event_id: SofaScore event ID

        Returns:
            Detailed event data or None if not found
        """
        endpoint = f"/event/{event_id}"

        return await self._make_request(endpoint)

    async def get_event_statistics(self, event_id: int) -> dict | None:
        """Get statistics for a specific event

        Args:
            event_id: SofaScore event ID

        Returns:
            Event statistics data or None if not found
        """
        endpoint = f"/event/{event_id}/statistics"

        return await self._make_request(endpoint)

    async def get_event_lineups(self, event_id: int) -> dict | None:
        """Get lineups for a specific event

        Args:
            event_id: SofaScore event ID

        Returns:
            Event lineups data or None if not found
        """
        endpoint = f"/event/{event_id}/lineups"

        return await self._make_request(endpoint)

    async def get_team_info(self, team_id: int) -> dict | None:
        """Get team information

        Args:
            team_id: SofaScore team ID

        Returns:
            Team information or None if not found
        """
        endpoint = f"/team/{team_id}"

        return await self._make_request(endpoint)

    async def find_team_by_name(self, team_name: str, sport: str = "football") -> dict | None:
        """Find a specific team by name and sport

        Args:
            team_name: Team name to search for
            sport: Sport name (default: football)

        Returns:
            Team dictionary if found, None otherwise
        """
        teams = await self.search_teams(team_name)

        if not teams:
            return None

        # Try exact match first (case insensitive)
        for team in teams:
            if team.get("name", "").lower() == team_name.lower():
                if sport and team.get("sport", "").lower() == sport.lower():
                    return team

        # Try partial match
        for team in teams:
            if team_name.lower() in team.get("name", "").lower():
                if sport and team.get("sport", "").lower() == sport.lower():
                    return team

        # Return first team if no exact match and sport filter matches
        for team in teams:
            if sport and team.get("sport", "").lower() == sport.lower():
                return team

        # Return first team if no sport filter
        return teams[0] if teams else None

    async def get_team_live_event(self, team_id: int, sport: str = "football") -> dict | None:
        """Get the currently in-progress event for a team, if any.

        Uses the live feed for the sport, which only contains matches that are
        in progress right now. This replaces the old
        /sport/{sport}/scheduled-events/{date} endpoint, which SofaScore
        removed (it now returns 404) and which downloaded the entire day's
        worldwide schedule on every poll.

        Args:
            team_id: SofaScore team ID
            sport: Sport slug (default: football)

        Returns:
            Live event data dictionary or None if the team is not playing now
        """
        data = await self._make_request(f"/sport/{sport}/events/live")

        if not data:
            return None

        for event in data.get("events", []):
            home_id = event.get("homeTeam", {}).get("id")
            away_id = event.get("awayTeam", {}).get("id")
            if team_id in (home_id, away_id):
                _LOGGER.debug("Found live event for team %s: %s", team_id, event.get("id"))
                return event

        return None

    async def get_event(self, event_id: int) -> dict | None:
        """Get a single event by ID.

        This is the cheap path used for repeated polling: roughly 3 KB per
        request, versus ~86 KB for the whole live feed. The response carries
        the live status, so a tracked fixture transitions from notstarted to
        inprogress to finished without any extra lookups.

        Args:
            event_id: SofaScore event ID

        Returns:
            Event dictionary or None if the event no longer exists
        """
        data = await self._make_request(f"/event/{event_id}")

        if not data:
            return None

        return data.get("event")
