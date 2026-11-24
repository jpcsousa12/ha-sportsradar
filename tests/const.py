"""Constants for tests."""

from unittest.mock import patch


class PlatformConfigType(dict):
    """Wrapper class to be able to add attributes on a dict."""

    def __init__(self, data=None, entry_id=None, **kwargs):
        super().__init__(**kwargs)
        self.data = data
        self.entry_id = entry_id


# Create the mock object
PLATFORM_TEST_DATA = [
    [
        PlatformConfigType(
            platform="sportsradar",
            league_id="BAD",
            team_id="MIA",
            name="test_tt_all_test03",
            conference_id="9999",
            timeout=1200,
            entry_id={},
            data={},
        ),
        False,
    ],
    [
        PlatformConfigType(
            platform="sportsradar",
            league_id="XXX",
            team_id="MIA",
            name="test_tt_all_test04",
            conference_id="9999",
            timeout=1200,
            entry_id={},
            data={},
        ),
        False,
    ],
    [
        PlatformConfigType(
            platform="sportsradar",
            league_id="MLB",
            team_id="MIA",
            name="test_tt_all_test02",
            conference_id="9999",
            timeout=1200,
            entry_id={},
            data={},
        ),
        True,
    ],
    [
        PlatformConfigType(
            platform="sportsradar",
            league_id="MLB",
            team_id="MIA",
            name="test_tt_all_test01",
            conference_id="9999",
            entry_id={},
            data={},
        ),
        True,
    ],
]

# SofaScore-shaped config entry. CONF_TEAM_ID holds a team NAME here, and the
# league fields are blanked because SofaScore resolves competitions itself.
CONFIG_DATA_SOFASCORE = {
    "team_id": "FC Porto",
    "sport_path": "football",
    "name": "test_tt_sofascore",
    "league_id": "",
    "league_path": "",
    "conference_id": "",
    "timeout": 120,
}


def patch_sofascore(team=None, live=None, next_event=None, event=None, stats=None):
    """Patch the SofaScore client so a test makes no network call.

    Returns started patchers; stop them in a finally block. Without this a test
    that merely sets up a config entry will really call the API, which is slow,
    flaky, and leaves lingering tasks that fail HA's teardown checks.
    """
    targets = {
        "find_team_by_name": team,
        "get_team_live_event": live,
        "get_team_next_event": next_event,
        "get_team_last_event": None,
        "get_event": event,
        "get_event_statistics": stats,
    }
    patchers = [
        patch(
            "custom_components.sportsradar.SofaScoreAPI.%s" % name, return_value=value
        )
        for name, value in targets.items()
    ]
    for patcher in patchers:
        patcher.start()
    return patchers
