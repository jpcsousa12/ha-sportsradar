"""Tests for SportsRadar setup, teardown and the call_api service.

The SofaScore client is patched throughout, so these make no network calls.
"""

import json
import os
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sportsradar.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.const import CONFIG_DATA_SOFASCORE

FIXTURES = os.path.join(os.path.dirname(__file__), "sofascore", "fixtures.json")

with open(FIXTURES, encoding="utf-8") as fh:
    FIX = json.load(fh)

PORTO = {"id": 3002, "name": "FC Porto", "slug": "fc-porto", "sport": "Football"}
OTHER = {"id": 3006, "name": "Benfica", "slug": "benfica", "sport": "Football"}


def _api_patches(team, live=None, next_event=None, event=None):
    return (
        patch(
            "custom_components.sportsradar.SofaScoreAPI.find_team_by_name",
            return_value=team,
        ),
        patch(
            "custom_components.sportsradar.SofaScoreAPI.get_team_live_event",
            return_value=live,
        ),
        patch(
            "custom_components.sportsradar.SofaScoreAPI.get_team_next_event",
            return_value=next_event,
        ),
        patch(
            "custom_components.sportsradar.SofaScoreAPI.get_team_last_event",
            return_value=None,
        ),
        patch(
            "custom_components.sportsradar.SofaScoreAPI.get_event",
            return_value=event,
        ),
        patch(
            "custom_components.sportsradar.SofaScoreAPI.get_event_statistics",
            return_value=None,
        ),
    )


@pytest.fixture(autouse=False)
def expected_lingering_timers() -> bool:
    """Temporary ability to bypass test failures due to lingering timers."""
    return False


async def test_setup_entry(hass, socket_enabled):
    """The entry sets up and produces one sensor showing the next fixture."""
    patches = _api_patches(
        PORTO, next_event=FIX["pre_event"], event=FIX["pre_event"]
    )
    for p in patches:
        p.start()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN, title="sports_radar", data=CONFIG_DATA_SOFASCORE
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        state = hass.states.get("sensor.test_tt_sofascore")
        assert state.state == "PRE"
        assert state.attributes.get("sport") == "football"
    finally:
        for p in patches:
            p.stop()


async def test_call_api_service_switches_team(hass, socket_enabled):
    """The call_api service repoints a sensor at a different team/sport.

    This also covers the cached fixture being dropped on reconfigure: without
    that, the sensor would keep showing the previous team's match.
    """
    patches = _api_patches(
        PORTO, next_event=FIX["pre_event"], event=FIX["pre_event"]
    )
    for p in patches:
        p.start()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN, title="sports_radar", data=CONFIG_DATA_SOFASCORE
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.test_tt_sofascore").state == "PRE"
    finally:
        for p in patches:
            p.stop()

    # Repoint at a team that is playing right now.
    live = FIX["live_event"]
    patches = _api_patches(OTHER, live=live, event=live)
    for p in patches:
        p.start()
    try:
        await hass.services.async_call(
            domain="sportsradar",
            service="call_api",
            service_data={
                "sport_path": "football",
                "league_path": "",
                "team_id": "Benfica",
            },
            target={"entity_id": ["sensor.test_tt_sofascore"]},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test_tt_sofascore")
        assert state.state == "IN"
    finally:
        for p in patches:
            p.stop()


async def test_unload_entry(hass, socket_enabled):
    """The entry unloads and removes its sensor."""
    patches = _api_patches(
        PORTO, next_event=FIX["pre_event"], event=FIX["pre_event"]
    )
    for p in patches:
        p.start()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN, title="sports_radar", data=CONFIG_DATA_SOFASCORE
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1

        assert await hass.config_entries.async_unload(entries[0].entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(DOMAIN)) == 0

        assert await hass.config_entries.async_remove(entries[0].entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    finally:
        for p in patches:
            p.stop()
