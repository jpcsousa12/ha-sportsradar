"""Home Assistant level tests for the SofaScore data source.

Each test requests `socket_enabled` because creating an event loop on
Windows needs a socketpair, which pytest-socket blocks by default. The
SofaScore client is patched, so no request leaves the machine.

These replace the ESPN-era assertions in test_init.py: they set the
integration up inside a real HA instance and check that it produces a sensor
with the right state, with the SofaScore API stubbed out so no network call is
made.
"""

import json
import os
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sportsradar.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

FIXTURES = os.path.join(os.path.dirname(__file__), "sofascore", "fixtures.json")

with open(FIXTURES, encoding="utf-8") as fh:
    FIX = json.load(fh)

PORTO_ID = 3002

CONFIG_SOFASCORE = {
    "team_id": "FC Porto",  # SofaScore mode: this is the team NAME
    "sport_path": "football",
    "name": "test_sofascore_porto",
    "league_id": "",
    "league_path": "",
    "conference_id": "",
    "timeout": 120,
}

TEAM_RESULT = {
    "id": PORTO_ID,
    "name": "FC Porto",
    "slug": "fc-porto",
    "sport": "Football",
    "country": "Portugal",
    "team_colors": {"primary": "#194f93", "secondary": "#ffffff"},
    "logo": "https://api.sofascore.com/api/v1/team/3002/image",
}


def _patch_api(live=None, next_event=None, event=None, stats=None):
    """Patch the SofaScore client so the integration never hits the network."""
    return (
        patch(
            "custom_components.sportsradar.SofaScoreAPI.find_team_by_name",
            return_value=TEAM_RESULT,
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
            return_value=stats,
        ),
    )


async def _setup(hass, **kwargs):
    patches = _patch_api(**kwargs)
    for p in patches:
        p.start()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN, title="sports_radar", data=CONFIG_SOFASCORE
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
    finally:
        for p in patches:
            p.stop()


async def test_integration_loads_and_creates_sensor(hass, socket_enabled):
    """The integration sets up and produces exactly one sensor."""
    await _setup(hass, next_event=FIX["pre_event"], event=FIX["pre_event"])

    assert "sportsradar" in hass.config.components
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1


async def test_upcoming_fixture_reports_pre(hass, socket_enabled):
    """An upcoming fixture lands on the sensor as PRE with both teams."""
    await _setup(hass, next_event=FIX["pre_event"], event=FIX["pre_event"])

    state = hass.states.get("sensor.test_sofascore_porto")
    assert state is not None
    assert state.state == "PRE"
    assert state.attributes.get("sport") == "football"
    assert state.attributes.get("team_name")
    assert state.attributes.get("opponent_name")


async def test_live_match_reports_in(hass, socket_enabled):
    """A match in progress reports IN - the case that was silently broken."""
    live = FIX["live_event"]
    await _setup(hass, live=live, event=live, stats=FIX["statistics_multi_period"])

    state = hass.states.get("sensor.test_sofascore_porto")
    assert state is not None
    assert state.state == "IN"


async def test_api_failure_does_not_report_a_phantom_game(hass, socket_enabled):
    """When SofaScore is unreachable the sensor must not claim 'no game'."""
    from custom_components.sportsradar.sofascore_api import SofaScoreApiError

    with patch(
        "custom_components.sportsradar.SofaScoreAPI.find_team_by_name",
        side_effect=SofaScoreApiError("403 Forbidden"),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN, title="sports_radar", data=CONFIG_SOFASCORE
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test_sofascore_porto")
        if state is not None:
            assert state.state != "PRE"


@pytest.mark.parametrize(
    "fixture_name,expected",
    [("pre_event", "PRE"), ("live_event", "IN"), ("finished_event", "POST")],
)
async def test_states_end_to_end(hass, socket_enabled, fixture_name, expected):
    """Each fixture shape maps to the expected sensor state inside HA."""
    event = FIX[fixture_name]
    live = event if expected == "IN" else None
    await _setup(hass, live=live, next_event=event, event=event)

    state = hass.states.get("sensor.test_sofascore_porto")
    assert state is not None
    assert state.state == expected


async def test_numeric_team_id_skips_the_search_endpoint(hass, socket_enabled):
    """A numeric team id must not call find_team_by_name.

    SofaScore returns 403 on /search/all from some hosts while the rest of the
    API keeps working, so configuring the id has to be a complete way around
    it.
    """
    config = dict(CONFIG_SOFASCORE)
    config["team_id"] = "3002"  # FC Porto, as an id rather than a name

    search_calls = []

    async def _must_not_be_called(*args, **kwargs):
        search_calls.append(args)
        raise AssertionError("find_team_by_name was called for a numeric id")

    patches = _patch_api(next_event=FIX["pre_event"], event=FIX["pre_event"])
    for p in patches:
        p.start()
    try:
        with patch(
            "custom_components.sportsradar.SofaScoreAPI.find_team_by_name",
            side_effect=_must_not_be_called,
        ):
            entry = MockConfigEntry(
                domain=DOMAIN, title="team_tracker", data=config
            )
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()

    assert not search_calls
    state = hass.states.get("sensor.test_sofascore_porto")
    assert state is not None
    assert state.state == "PRE"
