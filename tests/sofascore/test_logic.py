#!/usr/bin/env python3
"""Offline tests for the SofaScore API client and event processor.

Fixtures in fixtures.json are real responses captured from api.sofascore.com,
trimmed to the fields the integration reads. No network access is required,
so these run anywhere:

    python tests/sofascore/test_logic.py
"""

import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMPONENT = os.path.normpath(
    os.path.join(HERE, "..", "..", "custom_components", "sportsradar")
)
sys.path.insert(0, COMPONENT)

import sofascore_api  # noqa: E402
import sofascore_processor as proc  # noqa: E402
from sofascore_api import SofaScoreAPI, SofaScoreApiError  # noqa: E402

with open(os.path.join(HERE, "fixtures.json"), encoding="utf-8") as fh:
    FIX = json.load(fh)

PORTO = 3002
failures = []


def check(name, condition, detail=""):
    """Assert, and also print, so this file works under pytest AND standalone.

    Raising matters: pytest collects these functions, and a check that only
    recorded a failure in a list would let the suite report green while checks
    were failing.
    """
    if condition:
        print("  PASS  " + name)
        return
    print("  FAIL  " + name + " " + detail)
    failures.append(name)
    raise AssertionError("%s %s" % (name, detail))


class StubAPI(SofaScoreAPI):
    """API client with the HTTP layer replaced by fixtures."""

    def __init__(self, routes):
        super().__init__()
        self.routes = routes
        self.calls = []

    async def _make_request(self, endpoint, params=None):
        self.calls.append(endpoint)
        value = self.routes.get(endpoint, None)
        if isinstance(value, Exception):
            raise value
        return value


class FlakyResponse:
    def __init__(self, status):
        self.status = status
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return {"ok": True}


class FlakySession:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.attempts = 0
        self.closed = False

    def get(self, url, params=None, timeout=None):
        self.attempts += 1
        return FlakyResponse(self.statuses.pop(0))


async def test_status_mapping():
    print("")
    print("status mapping (uses status.type, not a hand-written code list)")
    cases = [
        (0, "notstarted", "PRE"),
        (6, "inprogress", "IN"),
        (7, "inprogress", "IN"),
        (20, "inprogress", "IN"),  # "Started" - absent from the old code list
        (31, "inprogress", "IN"),  # Halftime
        (100, "finished", "POST"),
        (120, "postponed", "POST"),
        (130, "canceled", "POST"),
    ]
    for code, status_type, expected in cases:
        got = proc.get_status_state(code, status_type)
        check(
            "code %s / %s -> %s" % (code, status_type, expected),
            got == expected,
            "(got %s)" % got,
        )


async def test_live_detection():
    print("")
    print("live detection via /sport/{sport}/events/live")
    api = StubAPI({"/sport/football/events/live": FIX["live_feed"]})

    hit = await api.get_team_live_event(1079435, "football")
    check(
        "finds a team that is playing now",
        hit is not None and hit["id"] == 17102712,
        "(got %s)" % hit,
    )

    miss = await api.get_team_live_event(PORTO, "football")
    check("returns None for a team that is not playing", miss is None, "(got %s)" % miss)

    away = await api.get_team_live_event(24259, "football")
    check(
        "matches on the away team too",
        away is not None and away["id"] == 16875507,
        "(got %s)" % away,
    )


async def test_single_event_fetch():
    print("")
    print("cheap single-event polling via /event/{id}")
    api = StubAPI({"/event/17102712": {"event": FIX["live_event"]}})

    event = await api.get_event(17102712)
    check(
        "unwraps the {'event': ...} envelope",
        event is not None and event.get("id") == 17102712,
        "(got %s)" % event,
    )
    check(
        "carries live status, so kickoff needs no extra call",
        event["status"]["type"] == "inprogress",
    )

    missing = StubAPI({})
    check("returns None when the event is gone (404)", await missing.get_event(999) is None)


async def test_last_event_ordering():
    print("")
    print("most-recent match from /team/{id}/events/last/0")
    api = StubAPI({"/team/%s/events/last/0" % PORTO: FIX["porto_last"]})
    event = await api.get_team_last_event(PORTO)
    check(
        "returns the tail (most recent), not events[0]",
        event is not None and event["id"] == 16432053,
        "(got %s)" % (event and event["id"]),
    )


async def test_error_handling():
    print("")
    print("error handling")
    api = StubAPI({"/boom": SofaScoreApiError("403 Forbidden")})
    try:
        await api._make_request("/boom")
        check("blocking errors raise instead of returning None", False)
    except SofaScoreApiError:
        check("blocking errors raise instead of returning None", True)

    empty = StubAPI({})
    check(
        "a 404 is reported as None, not an error",
        await empty.get_team_next_event(PORTO) is None,
    )


async def test_retry_and_backoff():
    print("")
    print("retry/backoff on transient failures")

    original_backoff = sofascore_api.BACKOFF_BASE
    sofascore_api.BACKOFF_BASE = 0  # keep the test fast

    try:
        api = SofaScoreAPI()
        session = FlakySession([429, 500, 200])
        api.session = session
        api._get_session = lambda: asyncio.sleep(0, result=session)

        result = await api._make_request("/retry-me")
        check("recovers after 429 then 500", result == {"ok": True}, "(got %s)" % result)
        check("made exactly 3 attempts", session.attempts == 3, "(got %s)" % session.attempts)

        api2 = SofaScoreAPI()
        session2 = FlakySession([500, 500, 500])
        api2.session = session2
        api2._get_session = lambda: asyncio.sleep(0, result=session2)
        try:
            await api2._make_request("/always-down")
            check("gives up with an error after repeated 5xx", False)
        except SofaScoreApiError:
            check("gives up with an error after repeated 5xx", True)
    finally:
        sofascore_api.BACKOFF_BASE = original_backoff


async def test_processing_end_to_end():
    print("")
    print("event processing (real payloads)")
    api = StubAPI({"/event/17102712/statistics": None})

    cases = [
        ("live match -> IN", "live_event", 1079435, "IN"),
        ("upcoming fixture -> PRE", "pre_event", PORTO, "PRE"),
        ("finished match -> POST", "finished_event", PORTO, "POST"),
    ]
    for label, fixture, team_id, expected in cases:
        values = await proc.async_process_sofascore_event(
            {}, "test_sensor", FIX[fixture], team_id, api
        )
        check(label, values.get("state") == expected, "(got %s)" % values.get("state"))

    live_values = await proc.async_process_sofascore_event(
        {}, "test_sensor", FIX["live_event"], 1079435, api
    )
    check(
        "live match requests rapid refresh",
        live_values.get("private_fast_refresh") is True,
    )

    pre_values = await proc.async_process_sofascore_event(
        {}, "test_sensor", FIX["pre_event"], PORTO, api
    )
    check(
        "fixture days away stays on the slow interval",
        pre_values.get("private_fast_refresh") is False,
    )

    fin = await proc.async_process_sofascore_event(
        {}, "test_sensor", FIX["finished_event"], PORTO, api
    )
    check(
        "tracked team recognised as the away side",
        fin.get("team_homeaway") == "away",
        "(got %s)" % fin.get("team_homeaway"),
    )
    check(
        "score read correctly (Porto won 4-1 at Casa Pia)",
        str(fin.get("team_score")) == "4" and str(fin.get("opponent_score")) == "1",
        "(got %s-%s)" % (fin.get("team_score"), fin.get("opponent_score")),
    )

    stats = await proc.async_get_sofascore_statistics(
        dict(live_values), 17102712, 1079435, api, "test_sensor"
    )
    check("missing statistics (404) degrades gracefully", isinstance(stats, dict))


async def test_statistics_periods():
    print("")
    print("statistics (real multi-period payload: Casa Pia 1-4 FC Porto)")
    api = StubAPI({"/event/16432053/statistics": FIX["statistics_multi_period"]})

    # Porto were away, so "our" stats are the away column of the ALL block:
    # possession 64%, total shots 17, on target 8.
    base = await proc.async_process_sofascore_event(
        {}, "test_sensor", FIX["finished_event"], PORTO, api
    )
    values = await proc.async_get_sofascore_statistics(
        base, 16432053, PORTO, api, "test_sensor"
    )

    check(
        "uses match totals, not the last period",
        str(values.get("team_total_shots")) == "17",
        "(got %s, 9 would mean 2nd-half-only)" % values.get("team_total_shots"),
    )
    check(
        "shots on target from the ALL block",
        str(values.get("team_shots_on_target")) == "8",
        "(got %s)" % values.get("team_shots_on_target"),
    )
    check(
        "possession from the ALL block",
        values.get("possession") == "64%",
        "(got %s)" % values.get("possession"),
    )
    check(
        "possession is not double-suffixed",
        "%%" not in str(values.get("possession")),
        "(got %s)" % values.get("possession"),
    )

    # A payload with no "ALL" block should still yield something sensible.
    only_second = {"statistics": [FIX["statistics_multi_period"]["statistics"][2]]}
    api2 = StubAPI({"/event/16432053/statistics": only_second})
    fallback = await proc.async_get_sofascore_statistics(
        dict(base), 16432053, PORTO, api2, "test_sensor"
    )
    check(
        "falls back to the first block when ALL is absent",
        fallback.get("possession") == "59%",
        "(got %s)" % fallback.get("possession"),
    )


async def main():
    tests = (
        test_status_mapping,
        test_live_detection,
        test_single_event_fetch,
        test_last_event_ordering,
        test_error_handling,
        test_retry_and_backoff,
        test_processing_end_to_end,
        test_statistics_periods,
    )
    for test in tests:
        try:
            await test()
        except AssertionError:
            pass  # already recorded and printed by check()

    print("")
    print("=" * 52)
    if failures:
        print("FAILED: %d check(s): %s" % (len(failures), ", ".join(failures)))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
