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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """ enable custom integrations """
    yield
