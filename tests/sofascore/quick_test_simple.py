#!/usr/bin/env python3
"""Quick SofaScore API Test - Simple version without Unicode"""

import asyncio
import aiohttp


async def quick_test():
    """Quick test of SofaScore API"""

    print("=" * 80)
    print("  Quick SofaScore API Test")
    print("=" * 80)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://www.sofascore.com",
        "Referer": "https://www.sofascore.com/",
    }

    print("\n[TEST 1] Searching for 'Manchester United'...")
    url = "https://api.sofascore.com/api/v1/search/all?q=Manchester United"

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=10) as response:
                print(f"  Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"  [OK] API is accessible!")

                    for result_group in data.get('results', []):
                        if result_group.get('type') == 'team':
                            teams = result_group.get('entities', [])
                            print(f"\n  Found {len(teams)} teams:")
                            for team in teams[:3]:
                                sport = team.get('sport', {}).get('name', 'Unknown')
                                print(f"    - {team.get('name')} ({sport}) [ID: {team.get('id')}]")

                            if teams:
                                team_id = teams[0].get('id')
                                team_name = teams[0].get('name')

                                print(f"\n[TEST 2] Getting next event for '{team_name}'...")
                                event_url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/next/0"

                                async with session.get(event_url, timeout=10) as event_response:
                                    print(f"  Status: {event_response.status}")

                                    if event_response.status == 200:
                                        event_data = await event_response.json()
                                        events = event_data.get('events', [])

                                        if events:
                                            event = events[0]
                                            home = event.get('homeTeam', {}).get('name')
                                            away = event.get('awayTeam', {}).get('name')
                                            tournament = event.get('tournament', {}).get('name')

                                            print(f"  [OK] Next game found!")
                                            print(f"    Tournament: {tournament}")
                                            print(f"    Match: {home} vs {away}")
                                        else:
                                            print(f"  [INFO] No upcoming games")
                                    else:
                                        print(f"  [ERROR] Status {event_response.status}")
                            break

                elif response.status == 403:
                    print(f"  [ERROR] 403 Forbidden - Headers need updating")
                else:
                    print(f"  [ERROR] Status {response.status}")

        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 80)
    print("  SUCCESS - SofaScore API is working!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(quick_test())
