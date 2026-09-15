#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for SofaScore integration
Run this to verify the API is working before deploying to Home Assistant
"""

import asyncio
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    except Exception:
        pass  # Fallback - use ASCII markers

# Add the custom_components directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(current_dir, '..', '..'))
sportsradar_path = os.path.join(repo_root, 'custom_components', 'sportsradar')
sys.path.insert(0, sportsradar_path)

# Now import the modules (without relative imports since we're running standalone)
import sofascore_api
import sofascore_processor
import clear_values

# Create aliases for easier use
SofaScoreAPI = sofascore_api.SofaScoreAPI
async_process_sofascore_event = sofascore_processor.async_process_sofascore_event
async_get_sofascore_statistics = sofascore_processor.async_get_sofascore_statistics
async_clear_values = clear_values.async_clear_values


def print_separator(title=""):
    """Print a nice separator"""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}")
    else:
        print(f"{'='*80}")


def print_team_info(team):
    """Print team information nicely"""
    print(f"\n  ID:      {team.get('id')}")
    print(f"  Name:    {team.get('name')}")
    print(f"  Sport:   {team.get('sport')}")
    print(f"  Country: {team.get('country')}")
    print(f"  Slug:    {team.get('slug')}")
    print(f"  Colors:  {team.get('team_colors')}")


def print_event_info(event):
    """Print event information nicely"""
    if not event:
        print("  No event data")
        return

    home = event.get('homeTeam', {})
    away = event.get('awayTeam', {})
    status = event.get('status', {})
    tournament = event.get('tournament', {})

    print(f"\n  Event ID:     {event.get('id')}")
    print(f"  Tournament:   {tournament.get('name', 'Unknown')}")
    print(f"  Status:       {status.get('description', 'Unknown')} (Code: {status.get('code')})")
    print(f"  Home Team:    {home.get('name', 'Unknown')}")
    print(f"  Away Team:    {away.get('name', 'Unknown')}")
    print(f"  Start Time:   {event.get('startTimestamp', 'Unknown')}")

    home_score = event.get('homeScore', {})
    away_score = event.get('awayScore', {})
    if home_score or away_score:
        print(f"  Score:        {home_score.get('current', 0)} - {away_score.get('current', 0)}")


def print_sensor_data(values):
    """Print processed sensor data"""
    important_keys = [
        'state', 'team_name', 'opponent_name', 'team_score', 'opponent_score',
        'date', 'kickoff_in', 'league', 'venue', 'location', 'quarter', 'clock',
        'team_logo', 'opponent_logo', 'event_url', 'api_message'
    ]

    print("\n  Key Sensor Attributes:")
    print(f"  {'─'*76}")
    for key in important_keys:
        if key in values:
            value = values[key]
            # Truncate long URLs
            if isinstance(value, str) and len(value) > 60:
                value = value[:57] + "..."
            print(f"  {key:20} : {value}")

    print(f"\n  Total attributes: {len(values)}")


async def test_team_search(api, team_name, sport="football"):
    """Test searching for a team"""
    print_separator(f"TEST 1: Searching for '{team_name}' in {sport}")

    teams = await api.search_teams(team_name)

    if not teams:
        print(f"\n  ❌ No teams found for '{team_name}'")
        return None

    print(f"\n  ✅ Found {len(teams)} team(s):")

    # Filter by sport
    sport_teams = [t for t in teams if t.get('sport', '').lower() == sport.lower()]

    if sport_teams:
        print(f"\n  Teams matching sport '{sport}':")
        for i, team in enumerate(sport_teams[:5], 1):  # Show max 5
            print(f"\n  [{i}]")
            print_team_info(team)

        return sport_teams[0]
    else:
        print(f"\n  ⚠️  No teams found for sport '{sport}'")
        print(f"\n  All teams found:")
        for i, team in enumerate(teams[:5], 1):
            print(f"\n  [{i}]")
            print_team_info(team)

        return teams[0] if teams else None


async def test_next_event(api, team_id, team_name):
    """Test getting current/next event for a team"""
    print_separator(f"TEST 2: Getting current/next event for team ID {team_id}")

    # Check for live game happening now
    print(f"\n  Checking for live game...")
    live_event = await api.get_team_live_event(team_id, 'football')

    if live_event:
        print(f"\n  [LIVE GAME DETECTED]")
        print_event_info(live_event)
        return live_event

    # No live game, get next event
    print(f"\n  No live game, checking next event...")
    event = await api.get_team_next_event(team_id)

    if not event:
        print(f"\n  ℹ️  No upcoming event found for '{team_name}'")
        print(f"  This is normal during off-season or if no games are scheduled.")
        return None

    print(f"\n  ✅ Found next event:")
    print_event_info(event)

    return event


async def test_last_event(api, team_id, team_name):
    """Test getting last event for a team"""
    print_separator(f"TEST 3: Getting last event for team ID {team_id}")

    event = await api.get_team_last_event(team_id)

    if not event:
        print(f"\n  ℹ️  No previous event found for '{team_name}'")
        return None

    print(f"\n  ✅ Found last event:")
    print_event_info(event)

    return event


async def test_event_processing(api, event, team_id):
    """Test processing event into sensor format"""
    print_separator(f"TEST 4: Processing event into sensor format")

    if not event:
        print("\n  ⚠️  Skipping - no event to process")
        return None

    # Initialize values
    values = await async_clear_values()

    # Process the event
    values = await async_process_sofascore_event(
        values=values,
        sensor_name="test_sensor",
        event=event,
        team_id=team_id,
        api_client=api,
    )

    print(f"\n  ✅ Event processed successfully")
    print_sensor_data(values)

    return values


async def test_statistics(api, event, team_id, values):
    """Test getting event statistics"""
    print_separator(f"TEST 5: Getting event statistics")

    if not event:
        print("\n  ⚠️  Skipping - no event")
        return

    event_id = event.get('id')
    if not event_id:
        print("\n  ⚠️  No event ID")
        return

    # Get statistics
    values_with_stats = await async_get_sofascore_statistics(
        values=values.copy(),
        event_id=event_id,
        team_id=team_id,
        api_client=api,
        sensor_name="test_sensor",
    )

    # Check if any stats were added
    stats_keys = ['team_shots_on_target', 'opponent_shots_on_target',
                  'team_total_shots', 'opponent_total_shots', 'possession']

    stats_found = {k: v for k, v in values_with_stats.items() if k in stats_keys and v}

    if stats_found:
        print(f"\n  ✅ Statistics retrieved:")
        for key, value in stats_found.items():
            print(f"  {key:25} : {value}")
    else:
        print("\n  ℹ️  No statistics available (normal for pre-game or some sports)")


async def test_multiple_teams(api, teams_to_test):
    """Test multiple teams"""
    print_separator(f"TEST 6: Testing multiple teams")

    results = []

    for team_name, sport in teams_to_test:
        print(f"\n\n  Testing: {team_name} ({sport})")
        print(f"  {'-'*76}")

        team = await api.find_team_by_name(team_name, sport)

        if team:
            team_id = team.get('id')
            print(f"  ✅ Found: {team.get('name')} (ID: {team_id})")

            event = await api.get_team_next_event(team_id)
            if event:
                home = event.get('homeTeam', {}).get('name')
                away = event.get('awayTeam', {}).get('name')
                print(f"  ✅ Next game: {home} vs {away}")
                results.append((team_name, "Found with upcoming game"))
            else:
                print(f"  ℹ️  No upcoming games")
                results.append((team_name, "Found but no upcoming game"))
        else:
            print(f"  ❌ Team not found")
            results.append((team_name, "Not found"))

    print(f"\n\n  Summary:")
    print(f"  {'-'*76}")
    for team_name, status in results:
        print(f"  {team_name:30} : {status}")


async def main():
    """Main test function"""
    print_separator("SofaScore API Test Script")
    print("\nThis script will test the SofaScore integration components")
    print("without requiring Home Assistant.\n")

    # Get team name from command line or use default
    if len(sys.argv) > 1:
        team_name = " ".join(sys.argv[1:])
        if ":" in team_name:
            team_name, sport = team_name.split(":", 1)
            sport = sport.strip()
        else:
            sport = "football"
    else:
        # Default test teams
        print("Usage: python test_sofascore.py <team_name> [:<sport>]")
        print("Example: python test_sofascore.py 'Manchester United'")
        print("Example: python test_sofascore.py 'Lakers':basketball")
        print("\nUsing default test: 'Manchester United'\n")
        team_name = "Manchester United"
        sport = "football"

    team_name = team_name.strip()

    # Initialize API client
    api = SofaScoreAPI(timeout=30)

    try:
        # Test 1: Search for team
        team = await test_team_search(api, team_name, sport)

        if not team:
            print("\n❌ Cannot continue without a valid team")
            return

        team_id = team.get('id')

        # Test 2: Get next event
        next_event = await test_next_event(api, team_id, team_name)

        # Test 3: Get last event (as fallback)
        last_event = None
        if not next_event:
            last_event = await test_last_event(api, team_id, team_name)

        # Use whichever event we have
        event_to_process = next_event or last_event

        # Test 4: Process event
        values = await test_event_processing(api, event_to_process, team_id)

        # Test 5: Get statistics
        if values and event_to_process:
            await test_statistics(api, event_to_process, team_id, values)

        # Test 6: Multiple teams (optional)
        print("\n\n")
        test_more = input("Test multiple teams? (y/n): ").strip().lower()
        if test_more == 'y':
            teams_to_test = [
                ("Barcelona", "football"),
                ("Real Madrid", "football"),
                ("Lakers", "basketball"),
                ("Manchester City", "football"),
                ("Bayern Munich", "football"),
            ]
            await test_multiple_teams(api, teams_to_test)

        print_separator("✅ All Tests Completed Successfully")
        print("\nThe SofaScore integration is working correctly!")
        print("You can now deploy this to Home Assistant.\n")

    except Exception as e:
        print_separator("❌ Error During Testing")
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        print("\nPlease check the error above and try again.\n")

    finally:
        # Close the API client
        await api.close()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
