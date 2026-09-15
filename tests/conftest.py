"""Fixtures for tests"""
import sys

import pytest
import pytest_socket

pytest_plugins = ("pytest_homeassistant_custom_component", "pytest_asyncio")


if sys.platform == "win32":
    # pytest-homeassistant-custom-component blocks sockets with
    # disable_socket(allow_unix_socket=True). On Linux that still allows the
    # AF_UNIX socketpair asyncio uses for its self-pipe, but Windows'
    # ProactorEventLoop builds that self-pipe over AF_INET, so the event loop
    # cannot even be created and every HA test errors during setup.
    #
    # Neutralise the block on Windows only. Tests here patch the SofaScore
    # client, so nothing reaches the network regardless.
    pytest_socket.disable_socket = lambda *args, **kwargs: None
    pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None


# Home Assistant's shared aiohttp session resolves names with aiohttp's
# AsyncResolver, which is backed by aiodns/pycares. That is right in
# production, but hostile to tests:
#
#   - on Linux, pycares starts a daemon thread that outlives the test, and
#     HA's teardown check fails on the lingering "_run_safe_shutdown_loop"
#   - on Windows, aiodns requires a SelectorEventLoop while HA's loop policy
#     hands pytest a ProactorEventLoop, so setting up any entry raises
#     "aiodns needs a SelectorEventLoop on Windows"
#
# Swap in the threaded resolver for tests. It only changes how names are
# resolved, and these tests patch the SofaScore client, so nothing is
# resolved at all.
import aiohttp.resolver  # noqa: E402
import homeassistant.helpers.aiohttp_client as _ha_aiohttp_client  # noqa: E402

_ha_aiohttp_client.AsyncResolver = aiohttp.resolver.ThreadedResolver


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """ enable custom integrations """
    yield


@pytest.fixture(autouse=True)
def clear_coordinator_caches():
    """Reset the coordinator's class-level caches between tests.

    data_cache/last_update/team_cache are shared by every coordinator instance
    and keyed on team+sport. That is deliberate at runtime - several sensors
    tracking one team share a single fetch - but between tests it lets one
    test's fixture data satisfy the next one's refresh.
    """
    from custom_components.sportsradar import SportsRadarDataUpdateCoordinator

    caches = (
        SportsRadarDataUpdateCoordinator.data_cache,
        SportsRadarDataUpdateCoordinator.last_update,
        SportsRadarDataUpdateCoordinator.team_cache,
    )
    for cache in caches:
        cache.clear()
    yield
    for cache in caches:
        cache.clear()
