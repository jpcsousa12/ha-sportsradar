""" TeamTracker Team Status """
import asyncio
from datetime import datetime, timezone
import locale
import logging

import arrow

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import ( # pylint: disable=reimported
    async_entries_for_config_entry,
    async_get,
    async_get as async_get_entity_registry,
)
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
    DEFAULT_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    LEAGUE_MAP,
    PLATFORMS,
    DEFAULT_REFRESH_RATE,
    POST_GAME_HOLD,
    RAPID_REFRESH_RATE,
    SERVICE_NAME_CALL_API,
    VERSION,
)
from .sofascore_api import SofaScoreAPI, SofaScoreApiError
from .sofascore_processor import async_process_sofascore_event, async_get_sofascore_statistics

_LOGGER = logging.getLogger(__name__)
# team_prob = {}
# oppo_prob = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""


    async def get_entry_id_from_entity_id(hass: HomeAssistant, entity_id: str):
        """Retrieve entry_id from entity_id."""
        # Get the entity registry
        entity_registry = async_get_entity_registry(hass)

        # Find the entry associated with the given entity_id
        entry = entity_registry.async_get(entity_id)

        if entry:
            return entry.config_entry_id

        return None


    async def async_call_api_service(call):
        """Handle the service action call."""

        sport_path = call.data.get(CONF_SPORT_PATH, "football")
        league_path = call.data.get(CONF_LEAGUE_PATH, "nfl")
        team_id = call.data.get(CONF_TEAM_ID, "cle")
        conference_id = call.data.get(CONF_CONFERENCE_ID, "")
        entity_ids = call.data.get("entity_id", "none")

        for entity_id in entity_ids:
            entry_id = await get_entry_id_from_entity_id(hass, entity_id)

            if entry_id: # Set up from UI, use entry_id as index
                sensor_coordinator = hass.data[DOMAIN][entry_id][COORDINATOR]
                sensor_coordinator.update_team_info(sport_path, league_path, team_id, conference_id)
                await sensor_coordinator.async_refresh()
            else: # Set up from YAML, use sensor_name (from entity_name) as index
                sensor_name = entity_id.split('.')[-1]
                if sensor_name in hass.data[DOMAIN] and COORDINATOR in hass.data[DOMAIN][sensor_name]:
                    sensor_coordinator = hass.data[DOMAIN][sensor_name][COORDINATOR]
                    sensor_coordinator.update_team_info(sport_path, league_path, team_id, conference_id)
                    await sensor_coordinator.async_refresh()
                else: # YAML had duplicate names so it doesn't match the entity_name
                    _LOGGER.info(
                        "%s: [service=call_api] No entry_id found (likely because of non-unique sensor names in YAML) for entity_id: %s",
                        sensor_name, 
                        entity_id,
                    )

    # Print startup message

    sensor_name = entry.data[CONF_NAME]

    _LOGGER.info(
        "%s: Setting up sensor from UI configuration using TeamTracker %s, if you have any issues please report them here: %s",
        sensor_name, 
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})

    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    if entry.unique_id is not None:
        _LOGGER.info(
            "%s: async_setup_entry() - entry.unique_id is not None: %s",
            sensor_name, 
            entry.unique_id,
        )
        hass.config_entries.async_update_entry(entry, unique_id=None)

        ent_reg = async_get(hass)
        for entity in async_entries_for_config_entry(ent_reg, entry.entry_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=entry.entry_id)

    # Setup the data coordinator
    coordinator = TeamTrackerDataUpdateCoordinator(
        hass, entry.data, entry
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    # For UI, use entry_id as index
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
#
#  Register services for sensor
#
    hass.services.async_register(DOMAIN, SERVICE_NAME_CALL_API, async_call_api_service,)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

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


class TeamTrackerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

    data_cache = {}
    last_update = {}
    c_cache = {}
    team_cache = {}  # Cache for team_name -> team_id mapping

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
        self.sofascore_api = SofaScoreAPI(timeout=DEFAULT_TIMEOUT)
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
    def update_team_info(self, sport_path, league_path, team_id, conference_id=""):
        """update team information when call_api service is called."""

        self.sport_path = sport_path
        # league_path is ignored in SofaScore mode
        self.team_id = team_id  # This is the team name in SofaScore mode

        # Clear cache for this team
        key = f"{team_id}:{sport_path}"
        if key in TeamTrackerDataUpdateCoordinator.data_cache:
            del TeamTrackerDataUpdateCoordinator.data_cache[key]

        # Clear team ID cache to force re-search
        team_cache_key = f"{team_id}:{sport_path}"
        if team_cache_key in TeamTrackerDataUpdateCoordinator.team_cache:
            del TeamTrackerDataUpdateCoordinator.team_cache[team_cache_key]

        # Forget the fixture we were following so the new team resolves fresh
        self.sofascore_event_id = None


    #
    #  Top-level method called from HA to update data for all teamtracker sensors
    #
    async def _async_update_data(self):
        """Update data."""
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            try:
                data = await self.async_update_game_data(self.config, self.hass)

                # update the interval based on flag
                if data["private_fast_refresh"]:
                    if self.update_interval != RAPID_REFRESH_RATE:
                        self.update_interval = RAPID_REFRESH_RATE
                        _LOGGER.debug(
                            "%s: Switching to rapid refresh rate (%s)", self.name, self.update_interval
                        )
                else:
                    if self.update_interval != DEFAULT_REFRESH_RATE:
                        self.update_interval = DEFAULT_REFRESH_RATE
                        _LOGGER.debug(
                            "%s: Switching to default refresh rate (%s)", self.name, self.update_interval
                        )
            except Exception as error:
                _LOGGER.debug("%s: Error updating data: %s", self.name, error)
                _LOGGER.debug("%s: Error type: %s", self.name, type(error).__name__)
                _LOGGER.debug("%s: Additional information: %s", self.name, str(error))
                raise UpdateFailed(error) from error
            return data

    async def async_update_game_data(self, config, hass) -> dict:
        """Update game data from data_cache or the API (if expired)"""

        sensor_name = self.name
        sport_path = self.sport_path
        team_name = self.team_id

        lang = self.get_lang()

        # Cache key is now based on team and sport
        key = f"{team_name}:{sport_path}"

        #
        #  Use cache if not expired
        #
        if key in self.data_cache:
            expiration = (
                datetime.fromisoformat(self.last_update[key]) + self.update_interval
            )
            now = datetime.now(timezone.utc)

            if now < expiration:
                data = self.data_cache[key]
                values = await self.async_update_values(config, hass, data, lang)
                if values.get("api_message"):
                    values["api_message"] = "Cached data: " + values["api_message"]
                else:
                    values["api_message"] = "Cached data"
                return values

        #
        #  Call the SofaScore API
        #

        data, file_override = await self.async_call_api(config, hass, lang)
        values = await self.async_update_values(config, hass, data, lang)
        self.data_cache[key] = data
        self.last_update[key] = values["last_update"]

        return values

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
            if cache_key in TeamTrackerDataUpdateCoordinator.team_cache:
                self.sofascore_team_id = TeamTrackerDataUpdateCoordinator.team_cache[cache_key]
                _LOGGER.debug(
                    "%s: Using cached team ID %s for '%s'",
                    sensor_name,
                    self.sofascore_team_id,
                    team_name,
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
                    TeamTrackerDataUpdateCoordinator.team_cache[cache_key] = self.sofascore_team_id
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
        except Exception as error:
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

        Order matters: a match that is in progress has already left the
        "next events" list, so the live feed is checked first. The most
        recent match is the final fallback so a just-finished result is not
        lost between fixtures.
        """
        event = await self.sofascore_api.get_team_live_event(
            self.sofascore_team_id, sport
        )

        if event:
            _LOGGER.info(
                "%s: Found LIVE event (ID: %s) for team '%s'",
                sensor_name,
                event.get("id"),
                team_name,
            )
        else:
            event = await self.sofascore_api.get_team_next_event(self.sofascore_team_id)

            if event:
                _LOGGER.debug(
                    "%s: Following next event (ID: %s) for team '%s'",
                    sensor_name,
                    event.get("id"),
                    team_name,
                )
            else:
                event = await self.sofascore_api.get_team_last_event(
                    self.sofascore_team_id
                )
                if event:
                    _LOGGER.debug(
                        "%s: No upcoming event for '%s', showing most recent (ID: %s)",
                        sensor_name,
                        team_name,
                        event.get("id"),
                    )

        if event:
            self.sofascore_event_id = event.get("id")
        else:
            self.sofascore_event_id = None
            _LOGGER.debug("%s: No event found for team '%s'", sensor_name, team_name)

        return event

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
        values["league_logo"] = DEFAULT_LOGO
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
