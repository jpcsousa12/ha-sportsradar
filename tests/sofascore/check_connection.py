#!/usr/bin/env python3
"""Check that this machine can actually reach SofaScore, using the exact
client the integration uses.

Run this ON the Home Assistant host before trusting the integration there:

    python tests/sofascore/check_connection.py "FC Porto"
    python tests/sofascore/check_connection.py "Lakers" basketball

SofaScore sits behind an edge cache that refuses some clients with HTTP 403
regardless of headers. That is network- and host-specific, so it has to be
checked from the machine that will run the integration.
"""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMPONENT = os.path.normpath(
    os.path.join(HERE, "..", "..", "custom_components", "sportsradar")
)
sys.path.insert(0, COMPONENT)

from sofascore_api import SofaScoreAPI, SofaScoreApiError  # noqa: E402
from sofascore_processor import (  # noqa: E402
    async_process_sofascore_event,
    async_get_sofascore_statistics,
)


async def main():
    team_name = sys.argv[1] if len(sys.argv) > 1 else "FC Porto"
    sport = sys.argv[2] if len(sys.argv) > 2 else "football"

    print("Checking SofaScore connectivity for %r (%s)" % (team_name, sport))
    print("-" * 60)

    api = SofaScoreAPI()
    ok = True

    try:
        # 1. Can we reach the API at all?
        team = await api.find_team_by_name(team_name, sport)
        if not team:
            print("FAIL  Reached the API but found no team called %r." % team_name)
            print("      Try the exact name SofaScore uses on its own site.")
            return 1
        team_id = team["id"]
        print("OK    API reachable - resolved %r to team id %s" % (team["name"], team_id))

        # 2. Is the team playing right now?
        live = await api.get_team_live_event(team_id, sport)
        if live:
            event = live
            print("OK    Live match in progress: %s (status: %s)" % (
                event.get("slug"), event.get("status", {}).get("description")))
        else:
            print("OK    Live feed reachable - no match in progress right now")
            event = await api.get_team_next_event(team_id)
            if event:
                print("OK    Next fixture: %s (event id %s)" % (
                    event.get("slug"), event.get("id")))
            else:
                event = await api.get_team_last_event(team_id)
                if event:
                    print("OK    No upcoming fixture; most recent: %s" % event.get("slug"))
                else:
                    print("WARN  No fixtures found at all for this team")
                    ok = False

        # 3. Does the cheap polling path work?
        if event:
            detail = await api.get_event(event["id"])
            if detail:
                print("OK    Single-event polling works (event %s)" % detail.get("id"))
            else:
                print("FAIL  Could not fetch event %s directly" % event["id"])
                ok = False

            # 4. Does it process into sensor values?
            values = await async_process_sofascore_event(
                {}, "check_connection", detail or event, team_id, api
            )
            print("OK    Processed into state=%s  %s %s-%s %s" % (
                values.get("state"),
                values.get("team_abbr") or values.get("team_name"),
                values.get("team_score"),
                values.get("opponent_score"),
                values.get("opponent_abbr") or values.get("opponent_name"),
            ))

            if values.get("state") == "IN":
                values = await async_get_sofascore_statistics(
                    values, detail.get("id"), team_id, api, "check_connection"
                )
                print("OK    Live statistics fetched (possession: %s)" % (
                    values.get("possession") or "n/a"))

    except SofaScoreApiError as error:
        print("FAIL  %s" % error)
        print("")
        print("      SofaScore refused or could not be reached from this host.")
        print("      If this is a 403, the API is blocking this client. The")
        print("      integration will report 'unavailable' rather than show a")
        print("      stale or empty game.")
        ok = False
    finally:
        await api.close()

    print("-" * 60)
    print("RESULT: %s" % ("usable from this host" if ok else "NOT usable from this host"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
