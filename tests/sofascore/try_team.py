#!/usr/bin/env python3
"""Try the SportsRadar integration against any team, from the console.

This runs the real integration code - the same API client and event processor
Home Assistant uses - so what you see here is what the sensor would show.

    # list teams playing right now, with their ids
    python tests/sofascore/try_team.py --live

    # by numeric SofaScore team id
    python tests/sofascore/try_team.py 3002

    # or by name
    python tests/sofascore/try_team.py "FC Porto"

    # follow a match, refreshing like the integration does
    python tests/sofascore/try_team.py 3002 --watch

    # other sports
    python tests/sofascore/try_team.py "Lakers" --sport basketball
    python tests/sofascore/try_team.py --live --sport basketball
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
COMPONENT = os.path.normpath(
    os.path.join(HERE, "..", "..", "custom_components", "sportsradar")
)
sys.path.insert(0, COMPONENT)

from sofascore_api import SPORT_MAP, SofaScoreAPI, SofaScoreApiError  # noqa: E402
from sofascore_processor import (  # noqa: E402
    async_get_sofascore_statistics,
    async_process_sofascore_event,
)

WIDTH = 64


def _supports_unicode():
    try:
        "─".encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


BAR = ("─" if _supports_unicode() else "-") * WIDTH


def _row(label, value):
    if value in (None, "", []):
        return
    print("  %-14s %s" % (label, value))


def _kickoff_phrase(start_timestamp):
    """Human phrase for how far away kick-off is."""
    if not start_timestamp:
        return None
    kickoff = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
    delta = kickoff - datetime.now(timezone.utc)
    seconds = int(delta.total_seconds())
    stamp = kickoff.strftime("%Y-%m-%d %H:%M UTC")

    if seconds < 0:
        seconds = -seconds
        suffix = "ago"
    else:
        suffix = "from now"

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    if days:
        rough = "%dd %dh" % (days, hours)
    elif hours:
        rough = "%dh %dm" % (hours, minutes)
    else:
        rough = "%dm" % minutes

    return "%s  (%s %s)" % (stamp, rough, suffix)


async def _resolve_team(api, target, sport):
    """Accept a numeric SofaScore id or a team name."""
    if str(target).isdigit():
        team_id = int(target)
        info = await api.get_team_info(team_id)
        if not info:
            return None, None
        team = info.get("team", info)
        return team_id, team.get("name", "team %s" % team_id)

    found = await api.find_team_by_name(str(target), sport)
    if not found:
        return None, None
    return found.get("id"), found.get("name")


async def _find_event(api, team_id, sport):
    """Same order the integration uses: live, then next, then most recent."""
    event = await api.get_team_live_event(team_id, sport)
    if event:
        return event, "live now"

    event = await api.get_team_next_event(team_id)
    if event:
        return event, "next fixture"

    event = await api.get_team_last_event(team_id)
    if event:
        return event, "most recent"

    return None, None


async def show_once(api, team_id, team_name, sport, quiet_header=False):
    """Fetch and print what the sensor would show. Returns True if live."""
    event, origin = await _find_event(api, team_id, sport)

    if not event:
        print("  No fixtures found for %s." % team_name)
        return False

    # Poll the single event, exactly as the integration does once it is
    # following a fixture.
    detail = await api.get_event(event["id"]) or event

    values = await async_process_sofascore_event(
        {}, "try_team", detail, team_id, api
    )

    state = values.get("state")
    if state == "IN":
        values = await async_get_sofascore_statistics(
            values, detail["id"], team_id, api, "try_team"
        )

    if not quiet_header:
        print(BAR)
        print("  %s  vs  %s" % (
            values.get("team_name") or "?", values.get("opponent_name") or "?"))
        print(BAR)

    _row("Competition", values.get("league"))
    _row("Source", origin)
    _row("State", state)

    if state == "PRE":
        _row("Kick-off", _kickoff_phrase(detail.get("startTimestamp")))
    else:
        _row("Score", "%s - %s" % (
            values.get("team_score"), values.get("opponent_score")))
        _row("Clock", values.get("clock"))
        _row("Period", values.get("quarter"))

    if state == "IN":
        _row("Possession", values.get("possession"))
        shots = values.get("team_total_shots")
        on_target = values.get("team_shots_on_target")
        if shots not in (None, ""):
            _row("Shots (us)", "%s total, %s on target" % (shots, on_target))
        shots = values.get("opponent_total_shots")
        on_target = values.get("opponent_shots_on_target")
        if shots not in (None, ""):
            _row("Shots (them)", "%s total, %s on target" % (shots, on_target))

    if state == "POST":
        if values.get("team_winner"):
            _row("Result", "%s won" % values.get("team_name"))
        elif values.get("opponent_winner"):
            _row("Result", "%s won" % values.get("opponent_name"))
        else:
            _row("Result", "draw")

    _row("Home/away", values.get("team_homeaway"))
    _row("Event id", detail.get("id"))
    if values.get("api_message"):
        _row("Note", values["api_message"])

    return state == "IN"


async def list_live(api, sport):
    """Show what is being played right now, so you can pick a team id."""
    # Diagnostic script: reaching for the raw endpoint keeps this honest about
    # what the integration's live check actually reads.
    data = await api._make_request("/sport/%s/events/live" % sport)
    events = (data or {}).get("events", [])

    if not events:
        print("Nothing live in %s right now." % sport)
        print("Try another sport: %s" % ", ".join(sorted(SPORT_MAP)))
        return

    print(BAR)
    print("  %d live %s match(es) - pass any id below" % (len(events), sport))
    print(BAR)
    for event in events:
        home = event.get("homeTeam", {})
        away = event.get("awayTeam", {})
        status = event.get("status", {}).get("description", "")
        print("  %-7s %-26s %s-%s  %-24s %s" % (
            home.get("id"),
            (home.get("name") or "")[:26],
            event.get("homeScore", {}).get("current", 0),
            event.get("awayScore", {}).get("current", 0),
            (away.get("name") or "")[:24],
            status,
        ))
    print(BAR)
    print("  e.g.  python tests/sofascore/try_team.py %s --watch"
          % events[0].get("homeTeam", {}).get("id"))


async def main():
    parser = argparse.ArgumentParser(
        description="Try the SportsRadar integration against any team.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "team", nargs="?",
        help="SofaScore team id (e.g. 3002) or team name (e.g. \"FC Porto\")",
    )
    parser.add_argument("--sport", default="football",
                        help="sport slug (default: football)")
    parser.add_argument("--live", action="store_true",
                        help="list teams playing right now, with their ids")
    parser.add_argument("--watch", "-w", action="store_true",
                        help="keep refreshing (5s while live, like the integration)")
    args = parser.parse_args()

    if not args.live and not args.team:
        parser.print_help()
        return 2

    api = SofaScoreAPI()
    try:
        if args.live:
            await list_live(api, args.sport)
            return 0

        team_id, team_name = await _resolve_team(api, args.team, args.sport)
        if not team_id:
            print("Could not find %r in %s." % (args.team, args.sport))
            print("Use --live to see what is on, or try the exact name "
                  "SofaScore uses.")
            return 1

        print("Resolved %r -> %s (id %s)" % (args.team, team_name, team_id))

        if not args.watch:
            await show_once(api, team_id, team_name, args.sport)
            return 0

        print("Watching - Ctrl+C to stop.")
        while True:
            print("")
            print("[%s]" % datetime.now().strftime("%H:%M:%S"))
            live = await show_once(api, team_id, team_name, args.sport)
            # 5s while a match is live, 60s otherwise. The integration uses
            # 5s / 10min; 60s just keeps this script responsive to kick-off.
            await asyncio.sleep(5 if live else 60)

    except SofaScoreApiError as error:
        print("")
        print("SofaScore error: %s" % error)
        print("If this is a 403, this host is being blocked by their edge "
              "cache.")
        return 1
    except KeyboardInterrupt:
        print("")
        print("Stopped.")
        return 0
    finally:
        await api.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("")
        print("Stopped.")
