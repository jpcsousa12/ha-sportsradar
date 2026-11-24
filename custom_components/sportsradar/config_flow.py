"""Config flow for Sports Radar."""

from __future__ import annotations

from typing import Any

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
    DEFAULT_NAME,
    DEFAULT_SPORT_PATH,
    DOMAIN,
    SPORT_OPTIONS,
)


def _get_schema(
    hass: HomeAssistant,
    user_input: dict[str, Any] | None,
    default_dict: dict[str, Any],
) -> vol.Schema:
    """Build the user step schema, defaulting to user_input then default_dict."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any:
        """Return the default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_TEAM_ID, default=_get_default(CONF_TEAM_ID)): cv.string,
            vol.Required(
                CONF_SPORT_PATH, default=_get_default(CONF_SPORT_PATH)
            ): vol.In(dict(SPORT_OPTIONS)),
            vol.Optional(CONF_NAME, default=_get_default(CONF_NAME)): cv.string,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class SportsRadarScoresFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for SportsRadar."""

    VERSION = 3

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            # ESPN-era keys, kept blank so entries keep the same shape
            user_input[CONF_LEAGUE_ID] = ""
            user_input[CONF_LEAGUE_PATH] = ""
            user_input[CONF_CONFERENCE_ID] = ""

            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):
        """Show the form asking for the team and sport."""
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow; HA provides it with self.config_entry."""
        return SportsRadarScoresOptionsFlow()


class SportsRadarScoresOptionsFlow(config_entries.OptionsFlow):
    """Options flow for SportsRadar."""

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **user_input}
            )

        lang = self.config_entry.options.get(CONF_API_LANGUAGE)
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_API_LANGUAGE,
                    description={"suggested_value": lang},
                    default="",
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors={},
        )
