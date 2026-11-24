""" SportsRadar Team Status """
import asyncio
from datetime import datetime, timezone
import locale
import logging

import arrow
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import (
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clear_values import async_clear_values
from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_LEAGUE,
    DEFAULT_LOGO,
    DEFAULT_SPORT_PATH,
    DEFAULT_TIMEOUT,
    FAILURE_BACKOFF,
    DOMAIN,
    ISSUE_URL,
    LEAGUE_MAP,
    PLATFORMS,
    DEFAULT_REFRESH_RATE,
    POST_GAME_HOLD,
    RAPID_REFRESH_RATE,
    SERVICE_NAME_CALL_API,
    SERVICE_NAME_DIAGNOSE,
    VERSION,
)
from .sofascore_api import SofaScoreAPI, SofaScoreApiError, async_diagnose_403
from .sofascore_processor import (
    apply_incidents,
    apply_lineups,
    async_get_sofascore_statistics,
    async_process_sofascore_event,
)

_LOGGER = logging.getLogger(__name__)

# Sensors are set up from config entries (or the YAML sensor platform); there
# is no `sportsradar:` top-level YAML key.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# league_path and conference_id are ESPN-era fields. They are still accepted
# so existing automations keep validating, but SofaScore needs neither.
CALL_API_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(CONF_TEAM_ID): cv.string,
        vol.Optional(CONF_SPORT_PATH, default=DEFAULT_SPORT_PATH): cv.string,
        vol.Optional(CONF_LEAGUE_PATH): cv.string,
        vol.Optional(CONF_CONFERENCE_ID): cv.string,
    }
)


def get_entry_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the config entry id that owns entity_id, if any."""
    entity_entry = async_get_entity_registry(hass).async_get(entity_id)
    return entity_entry.config_entry_id if entity_entry else None


def _coordinator_for_entity(hass: HomeAssistant, entity_id: str):
    """Find the coordinator behind a sensor, set up from the UI or YAML."""
    domain_data = hass.data.get(DOMAIN, {})

    # UI entries are indexed by entry id, YAML sensors by sensor name, which
    # is assumed to match the entity's object id.
    key = get_entry_id_from_entity_id(hass, entity_id) or entity_id.split(".")[-1]
    return domain_data.get(key, {}).get(COORDINATOR)


async def async_call_api_service(call: ServiceCall) -> None:
    """Point the targeted sensors at another team and refresh them."""
    hass = call.hass
    sport_path = call.data[CONF_SPORT_PATH]
    team_id = call.data[CONF_TEAM_ID]

    for entity_id in await async_extract_entity_ids(hass, call):
        coordinator = _coordinator_for_entity(hass, entity_id)
        if coordinator is None:
            # A YAML sensor whose name does not match its entity id (for
            # example because names were duplicated), or not our entity.
            _LOGGER.info(
                "[service=call_api] No Sports Radar sensor found for %s",
                entity_id,
            )
            continue
        coordinator.update_team_info(sport_path, team_id)
        await coordinator.async_refresh()


async def async_diagnose_service(call: ServiceCall) -> None:
    """Report which client configurations SofaScore accepts from this host.

    Runs in Home Assistant's own process, so the Python build, OpenSSL and
    network path are exactly the ones the integration uses. Results go to
    the log at error level so they are visible without enabling debug.
    """
    results = await async_diagnose_403()

    _LOGGER.error("Sports Radar connectivity diagnosis:")
    for label, outcome in results:
        verdict = "ALLOWED" if outcome == 200 else "refused"
        _LOGGER.error("  %-44s %s (%s)", label, verdict, outcome)

    if any(outcome == 200 for _, outcome in results):
        _LOGGER.error(
            "  At least one configuration works from this host - report "
            "which, and the integration can use it."
        )
    else:
        _LOGGER.error(
            "  Every configuration was refused. This host is blocked by "
            "SofaScore; no change to the integration will fix that."
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's services, once for all sensors."""
    hass.services.async_register(
        DOMAIN, SERVICE_NAME_CALL_API, async_call_api_service, schema=CALL_API_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_NAME_DIAGNOSE, async_diagnose_service)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a sensor from a config entry."""
    sensor_name = entry.data[CONF_NAME]

    _LOGGER.info(
        "%s: Setting up sensor from UI configuration using SportsRadar %s, if you have any issues please report them here: %s",
        sensor_name,
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})

    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    coordinator = SportsRadarDataUpdateCoordinator(hass, entry.data, entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    # For UI, use entry_id as index
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


#
#  Only needed if Options Flow is added
#
async def update_options_listener(hass, entry):
    """Update listener."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    sensor_name = entry.data[CONF_NAME]
    version = entry.version

    # 1-> 2->3: Migration format
    # Add CONF_LEAGUE_ID, CONF_SPORT_PATH, and CONF_LEAGUE_PATH if not already populated
    if version < 3:
        _LOGGER.debug("%s: Migrating from version %s", sensor_name, version)
        updated_config = entry.data.copy()

        if CONF_LEAGUE_ID not in updated_config.keys():
            updated_config[CONF_LEAGUE_ID] = DEFAULT_LEAGUE
        if (CONF_SPORT_PATH not in updated_config.keys()) or (
            CONF_LEAGUE_PATH not in updated_config.keys()
        ):
            league_id = updated_config[CONF_LEAGUE_ID].upper()
            updated_config.update(LEAGUE_MAP[league_id])

        if updated_config != entry.data:
            hass.config_entries.async_update_entry(entry, data=updated_config, version=3)

        _LOGGER.debug("%s: Migration to version %s complete", sensor_name, entry.version)

    return True


class SportsRadarDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SportsRadar data."""

    # "team name:sport" -> SofaScore team id. Shared on purpose: the id of a
    # team never changes, so every coordinator can reuse a lookup.
    team_cache = {}

    def __init__(self, hass, config, entry: ConfigEntry=None):
        """Initialize."""
        self.name = config[CONF_NAME]
        self.api_url = ""
        self.league_id = config.get(CONF_LEAGUE_ID, "")
        self.league_path = config.get(CONF_LEAGUE_PATH, "")
        self.sport_path = config.get(CONF_SPORT_PATH, "football")
        self.team_id = config[CONF_TEAM_ID]
        self.conference_id = ""
        if CONF_CONFERENCE_ID in config.keys():
            if len(config[CONF_CONFERENCE_ID]) > 0:
                self.conference_id = config[CONF_CONFERENCE_ID]

        self.config = config
        self.hass = hass
        self.entry = entry #None if setup from YAML

        # Initialize SofaScore API client
        # Use Home Assistant's shared session: it carries HA's DNS
        # resolver and SSL context, and HA closes it on shutdown.
        self.sofascore_api = SofaScoreAPI(
            timeout=DEFAULT_TIMEOUT, session=async_get_clientsession(hass)
        )
        self.sofascore_team_id = None  # Will be populated after team search
        self.sofascore_event_id = None  # Fixture currently being tracked

        super().__init__(hass, _LOGGER, name=self.name, update_interval=DEFAULT_REFRESH_RATE)
        _LOGGER.debug(
            "%s: Using default refresh rate (%s)", self.name, self.update_interval
        )


    #
    #  Return the language to use for the API
    #
    def get_lang(self):
        """Return language to use for API."""

        try:
            lang = self.hass.config.language
        except:
            lang, _ = locale.getlocale()
            lang = lang or "en_US"

        # Override language if is set in the configuration or options

        if CONF_API_LANGUAGE in self.config.keys():
            lang = self.config[CONF_API_LANGUAGE].lower()
        if self.entry and self.entry.options and CONF_API_LANGUAGE in self.entry.options and len(self.entry.options[CONF_API_LANGUAGE])>=2:
                lang = self.entry.options[CONF_API_LANGUAGE].lower()

        return lang


    #
    #  Set team info from service call
    #
    def update_team_info(self, sport_path, team_id):
        """Update team information when the call_api service is called."""

        self.sport_path = sport_path
        self.team_id = team_id  # a team name, or a SofaScore numeric id

        # Clear team ID cache to force re-search
        team_cache_key = f"{team_id}:{sport_path}"
        if team_cache_key in SportsRadarDataUpdateCoordinator.team_cache:
            del SportsRadarDataUpdateCoordinator.team_cache[team_cache_key]

        # Forget the fixture we were following so the new team resolves fresh
        self.sofascore_event_id = None


    #
    #  Top-level method called from HA to update data for all sportsradar sensors
    #
    async def _async_update_data(self):
        """Fetch new data, adapting the polling interval to the match state."""
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                data = await self.async_update_game_data(self.config, self.hass)
        except Exception as error:
            self._back_off()
            # This is why the entity goes unavailable, so say it plainly
            # and at a level that shows up without enabling debug logging.
            _LOGGER.error(
                "%s: Update failed, sensor will show as unavailable. %s: %s",
                self.name,
                type(error).__name__,
                error,
            )
            _LOGGER.debug("%s: Update failure details", self.name, exc_info=True)
            raise UpdateFailed(error) from error

        wanted = RAPID_REFRESH_RATE if data["private_fast_refresh"] else DEFAULT_REFRESH_RATE
        if self.update_interval != wanted:
            self.update_interval = wanted
            _LOGGER.debug("%s: Refresh rate is now %s", self.name, self.update_interval)
        return data

    def _back_off(self):
        """Slow down after a failed update.

        A failure during a live match would otherwise keep retrying every few
        seconds, which is exactly what gets a client blocked by SofaScore.
        The interval doubles from FAILURE_BACKOFF up to the default rate, and
        the next successful update puts it back where the match needs it.
        """
        backoff = min(
            DEFAULT_REFRESH_RATE, max(FAILURE_BACKOFF, self.update_interval * 2)
        )
        if self.update_interval != backoff:
            self.update_interval = backoff
            _LOGGER.debug("%s: Backing off to %s after a failure", self.name, backoff)

    async def async_update_game_data(self, config, hass) -> dict:
        """Fetch the tracked fixture from SofaScore and build the values."""
        lang = self.get_lang()
        data, _ = await self.async_call_api(config, hass, lang)
        return await self.async_update_values(config, hass, data, lang)

    #
    #  Call the SofaScore API to get team's next event
    #
    async def async_call_api(self, config, hass, lang) -> dict:
        """Query SofaScore API for team's next event."""

        sensor_name = self.name
        team_name = self.team_id  # In SofaScore mode, team_id is actually the team name
        sport = self.sport_path

        data = None

        try:
            # Check if we have cached team ID
            cache_key = f"{team_name}:{sport}"
            if cache_key in SportsRadarDataUpdateCoordinator.team_cache:
                self.sofascore_team_id = SportsRadarDataUpdateCoordinator.team_cache[cache_key]
                _LOGGER.debug(
                    "%s: Using cached team ID %s for '%s'",
                    sensor_name,
                    self.sofascore_team_id,
                    team_name,
                )
            elif str(team_name).strip().isdigit():
                # A numeric value is a SofaScore team id, so the search
                # endpoint can be skipped entirely. That matters because
                # /search/all is the endpoint SofaScore blocks first: some
                # hosts get 403 there while every other endpoint works.
                self.sofascore_team_id = int(str(team_name).strip())
                SportsRadarDataUpdateCoordinator.team_cache[cache_key] = (
                    self.sofascore_team_id
                )
                _LOGGER.info(
                    "%s: Using SofaScore team id %s directly (no search)",
                    sensor_name,
                    self.sofascore_team_id,
                )
            else:
                # Search for team
                _LOGGER.debug(
                    "%s: Searching for team '%s' in sport '%s'",
                    sensor_name,
                    team_name,
                    sport,
                )

                team_data = await self.sofascore_api.find_team_by_name(team_name, sport)

                if team_data:
                    self.sofascore_team_id = team_data.get("id")
                    SportsRadarDataUpdateCoordinator.team_cache[cache_key] = self.sofascore_team_id
                    _LOGGER.info(
                        "%s: Found team '%s' with ID %s",
                        sensor_name,
                        team_data.get("name"),
                        self.sofascore_team_id,
                    )
                else:
                    _LOGGER.warning(
                        "%s: Could not find team '%s' in sport '%s'",
                        sensor_name,
                        team_name,
                        sport,
                    )
                    self.api_url = "SofaScore Team Search"
                    return None, False

            # Resolve the fixture to show.
            #
            # Cheap path first: if we are already following a fixture, poll
            # that single event (~3 KB). Its status carries the match from
            # notstarted -> inprogress -> finished, so kickoff is detected
            # without scanning any feed.
            if self.sofascore_team_id:
                data = await self._async_get_tracked_event(sensor_name)

                if data is None:
                    data = await self._async_resolve_event(sensor_name, team_name, sport)

                self.api_url = f"SofaScore API - Team ID: {self.sofascore_team_id}"


        except SofaScoreApiError:
            # Reachability/blocking problem - let it bubble up so the
            # coordinator raises UpdateFailed and HA marks the sensor
            # unavailable, rather than silently showing "no game".
            self.api_url = "SofaScore API Error"
            raise
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Deliberately broad: an unexpected client-side failure should
            # leave the sensor without a game, not break every other sensor.
            _LOGGER.error(
                "%s: Error calling SofaScore API for '%s': %s",
                sensor_name,
                team_name,
                error,
            )
            data = None
            self.api_url = "SofaScore API Error"

        return data, False

    @staticmethod
    def _is_finished(event) -> bool:
        """True if the fixture is over (finished, postponed or cancelled)."""
        status_type = (event.get("status", {}).get("type") or "").lower()
        return status_type in ("finished", "canceled", "cancelled", "postponed")

    async def _async_get_tracked_event(self, sensor_name):
        """Poll the fixture we are already following.

        Returns the event, or None when we should look for a different one.
        """
        if not self.sofascore_event_id:
            return None

        event = await self.sofascore_api.get_event(self.sofascore_event_id)

        if not event:
            _LOGGER.debug(
                "%s: Tracked event %s no longer available, re-resolving",
                sensor_name,
                self.sofascore_event_id,
            )
            self.sofascore_event_id = None
            return None

        if self._is_finished(event):
            # Keep the result on the sensor for a while, then move on to the
            # next fixture.
            start = event.get("startTimestamp")
            if start:
                ended_around = datetime.fromtimestamp(start, tz=timezone.utc)
                if datetime.now(timezone.utc) - ended_around > POST_GAME_HOLD:
                    _LOGGER.debug(
                        "%s: Tracked event %s finished and hold expired, re-resolving",
                        sensor_name,
                        self.sofascore_event_id,
                    )
                    self.sofascore_event_id = None
                    return None

        return event

    async def _async_resolve_event(self, sensor_name, team_name, sport):
        """Find which fixture to follow, and remember it.

        Team-scoped endpoints are tried first. They are cheaper, and they are
        also the ones that keep working when SofaScore blocks a host: some
        hosts get 403 on the broad feeds (/search/all, /sport/*/events/live)
        while /team/{id}/... and /event/{id} still answer normally.

        A match that is in progress has already left the "next events" list,
        but it does appear as the most recent entry of the "last events" list,
        so live detection does not actually need the live feed.
        """
        event = None

        recent = await self.sofascore_api.get_team_last_event(self.sofascore_team_id)

        if recent and not self._is_finished(recent):
            _LOGGER.info(
                "%s: Found LIVE event (ID: %s) for team '%s'",
                sensor_name,
                recent.get("id"),
                team_name,
            )
            event = recent
        else:
            event = await self.sofascore_api.get_team_next_event(self.sofascore_team_id)

            if event:
                _LOGGER.debug(
                    "%s: Following next event (ID: %s) for team '%s'",
                    sensor_name,
                    event.get("id"),
                    team_name,
                )
            elif recent:
                _LOGGER.debug(
                    "%s: No upcoming event for '%s', showing most recent (ID: %s)",
                    sensor_name,
                    team_name,
                    recent.get("id"),
                )
                event = recent

        if event is None:
            # Last resort only. Guarded because this feed is the first thing
            # SofaScore blocks, and a block here must not fail the update when
            # the team endpoints answered.
            try:
                event = await self.sofascore_api.get_team_live_event(
                    self.sofascore_team_id, sport
                )
            except SofaScoreApiError as error:
                _LOGGER.debug(
                    "%s: Live feed unavailable (%s); relying on team endpoints",
                    sensor_name,
                    error,
                )

        if event:
            self.sofascore_event_id = event.get("id")

            # The list endpoints return a trimmed event: no venue, no city.
            # Fetch the full record now so the first update is complete,
            # rather than leaving those blank until the next refresh.
            detail = await self.sofascore_api.get_event(self.sofascore_event_id)
            if detail:
                event = detail
        else:
            self.sofascore_event_id = None
            _LOGGER.debug("%s: No event found for team '%s'", sensor_name, team_name)

        return event

    async def _async_get_lineups(self, event_id, sensor_name):
        """Line-ups for an event, fetched once it has kit colours.

        The shirts worn do not change during a game, so once SofaScore has
        published them they are kept; before that, retry every 5 minutes.
        """
        cache = self.__dict__.setdefault("_lineups_cache", {})
        now = datetime.now(timezone.utc).timestamp()
        cached = cache.get(event_id)
        if cached:
            data, fetched_at = cached
            has_kits = bool(data and (data.get("home") or {}).get("playerColor"))
            if has_kits or now - fetched_at < 300:
                return data
        try:
            data = await self.sofascore_api.get_event_lineups(event_id)
        except SofaScoreApiError as error:
            _LOGGER.debug("%s: Line-ups unavailable: %s", sensor_name, error)
            data = None
        cache.clear()  # only the current fixture is worth keeping
        cache[event_id] = (data, now)
        return data

    async def _async_add_match_details(self, values, data, sensor_name):
        """Kit colours/formation (from 2h before kickoff) and last_play.

        Optional extras: a failure here is logged and never fails the update.
        """
        try:
            await self._async_add_match_details_unguarded(values, data, sensor_name)
        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("%s: Could not add match details: %s", sensor_name, error)

    async def _async_add_match_details_unguarded(self, values, data, sensor_name):
        """Fetch line-ups and incidents and apply them to values."""
        state = values.get("state")
        event_id = data.get("id") if data else None
        if not event_id or state not in ("PRE", "IN", "POST"):
            return

        start = data.get("startTimestamp") or 0
        now = datetime.now(timezone.utc).timestamp()
        if state != "PRE" or 0 <= start - now <= 2 * 3600:
            apply_lineups(values, await self._async_get_lineups(event_id, sensor_name))

        if state in ("IN", "POST"):
            try:
                incidents = await self.sofascore_api.get_event_incidents(event_id)
            except SofaScoreApiError as error:
                _LOGGER.debug("%s: Incidents unavailable: %s", sensor_name, error)
                incidents = None
            apply_incidents(
                values,
                incidents,
                (data.get("homeTeam") or {}).get("name", ""),
                (data.get("awayTeam") or {}).get("name", ""),
            )

    async def async_update_values(self, config, hass, data, lang) -> dict:
        """Return values based on the data passed into method"""

        values = {}
        sensor_name = self.name
        sport_path = self.sport_path
        team_name = self.team_id

        values = await async_clear_values()
        values["sport"] = sport_path
        values["sport_path"] = self.sport_path
        values["league"] = ""
        values["league_path"] = ""
        values["league_logo"] = ""
        values["team_abbr"] = team_name[:3].upper() if len(team_name) >= 3 else team_name.upper()
        values["state"] = "NOT_FOUND"
        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        values["private_fast_refresh"] = False
        values["api_url"] = self.api_url

        if data is None:
            values["api_message"] = "No upcoming event found for this team"
            _LOGGER.debug(
                "%s: No event data returned for team '%s'", sensor_name, team_name
            )
            return values

        # Process SofaScore event
        values = await async_process_sofascore_event(
            values,
            sensor_name,
            data,
            self.sofascore_team_id,
            self.sofascore_api,
        )

        await self._async_add_match_details(values, data, sensor_name)

        # If event is IN or coming soon, fetch additional statistics
        if values.get("state") == "IN" and data:
            event_id = data.get("id")
            if event_id:
                values = await async_get_sofascore_statistics(
                    values,
                    event_id,
                    self.sofascore_team_id,
                    self.sofascore_api,
                    sensor_name,
                )

        return values
