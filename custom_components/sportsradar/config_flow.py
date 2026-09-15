"""Adds config flow for SportsRadar."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_LEAGUE,
    DEFAULT_NAME,
    DEFAULT_SPORT_PATH,
    DOMAIN,
    LEAGUE_MAP,
    SPORT_OPTIONS,
)

JSON_FEATURES = "features"
JSON_PROPERTIES = "properties"
JSON_ID = "id"

_LOGGER = logging.getLogger(__name__)


def _get_schema(
    hass: HomeAssistant,
    user_input: Optional[Dict[str, Any]],
    default_dict: Dict[str, Any],
    entry_id: str = None,
) -> vol.Schema:
    # pylint: disable=deprecated-typing-alias
    # pylint: disable=consider-alternative-union-syntax
    """Gets a schema using the default_dict as a backup."""

    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Gets default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    # Create sport selector dictionary
    sport_dict = {sport_id: sport_name for sport_id, sport_name in SPORT_OPTIONS}

    return vol.Schema(
        {
            vol.Required(CONF_TEAM_ID, default=_get_default(CONF_TEAM_ID)): cv.string,
            vol.Required(CONF_SPORT_PATH, default=_get_default(CONF_SPORT_PATH)): vol.In(sport_dict),
            vol.Optional(CONF_NAME, default=_get_default(CONF_NAME)): cv.string,
        }
    )


def _get_path_schema(hass: Any, user_input: list, default_dict: list) -> Any:
    """Gets a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key):
        """Gets default value for key."""
        return user_input.get(key, default_dict.get(key))

    return vol.Schema(
        {
            vol.Required(CONF_SPORT_PATH, default=_get_default(CONF_SPORT_PATH)): str,
            vol.Required(CONF_LEAGUE_PATH, default=_get_default(CONF_LEAGUE_PATH)): str,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class SportsRadarScoresFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for SportsRadar."""

    VERSION = 3
#    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            # Set empty league values for SofaScore mode
            user_input[CONF_LEAGUE_ID] = ""
            user_input[CONF_LEAGUE_PATH] = ""
            user_input[CONF_CONFERENCE_ID] = ""

            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data[CONF_NAME], data=self._data
            )

        return await self._show_config_form(user_input)

    async def async_step_path(self, user_input: Optional[Dict[str, Any]] = None):
        # pylint: disable=deprecated-typing-alias
        # pylint: disable=consider-alternative-union-syntax

        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return await self._show_path_form(user_input)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""

        # Defaults
        defaults = {
            CONF_SPORT_PATH: DEFAULT_SPORT_PATH,
            CONF_NAME: DEFAULT_NAME,
            CONF_TEAM_ID: "",
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema(self.hass, user_input, defaults),
            errors=self._errors,
            description_placeholders={
                "team_example": "e.g., 'Manchester United', 'Barcelona', 'Real Madrid'",
            },
        )

    async def _show_path_form(self, user_input):
        """Show the path form to edit path data."""

        # Defaults
        defaults = {
            CONF_SPORT_PATH: "",
            CONF_LEAGUE_PATH: "",
        }
        return self.async_show_form(
            step_id="path",
            data_schema=_get_path_schema(self.hass, user_input, defaults),
            errors=self._errors,
        )


    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SportsRadarScoresOptionsFlow(config_entry)

class SportsRadarScoresOptionsFlow(config_entries.OptionsFlow):
    """Options flow for SportsRadar."""

    def __init__(self, config_entry):
        """Initialize."""
        self.entry = config_entry
        self._options = dict(config_entry.options)
        self._errors = {}

    async def async_step_init(self, user_input=None):
        """Manage options."""

        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)
        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input):
        """Show the options form to edit location data."""

        lang = None
        if self.entry and self.entry.options and CONF_API_LANGUAGE in self.entry.options:
                lang = self.entry.options[CONF_API_LANGUAGE]

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_API_LANGUAGE, description={"suggested_value": lang}, default=""): cv.string,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=self._errors,
        )