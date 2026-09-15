""" Test SportsRadar Sensor """

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from typing import Any
from custom_components.sportsradar.const import DOMAIN
from custom_components.sportsradar.sensor import async_setup_platform
from tests.const import CONFIG_DATA_SOFASCORE, PLATFORM_TEST_DATA, patch_sofascore


@pytest.fixture(autouse=False)
def expected_lingering_timers() -> bool:
    """"  Temporary ability to bypass test failures due to lingering timers.
        Parametrize to True to bypass the pytest failure.
        @pytest.mark.parametrize("expected_lingering_timers", [True])
        This should be removed when all lingering timers have been cleaned up.
    """
    return False


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_sensor(hass, mocker):
    """ test sensor """

    patchers = patch_sofascore()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="FC Porto",
            data=CONFIG_DATA_SOFASCORE,
        )

        mocker.patch("locale.getlocale", return_value=("en", 0))

        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        for patcher in patchers:
            patcher.stop()

    assert "sportsradar" in hass.config.components

#    assert await entry.async_unload(hass)
#    await hass.async_block_till_done()


async def test_setup_platform(hass):
    """test platform setup"""

# Mock implementation of async_add_entities callback
    entity_list = []
    async def mock_async_add_entities_callback(entities: list[Any], update_before_add: bool = False) -> None:
        """Mock implementation of the async_add_entities callback."""
        # Simulate async_add_entities callback behavior
        entity_list.extend(entities)
        print(f"Adding entities: {entity_list}")

    for test in PLATFORM_TEST_DATA:
        await async_setup_platform(
            hass,
            test[0],
            mock_async_add_entities_callback,
            discovery_info=None,
        )

        assert (DOMAIN in hass.data) == test[1]
