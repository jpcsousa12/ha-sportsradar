# Installation & Testing Guide

## 🧪 Step 1: Test Locally (Before Installing to Home Assistant)

### Option A: Quick Test (Windows)
```bash
# Double-click this file:
run_tests.bat

# Or run from command line:
cd C:\Users\joao.sousa\PycharmProjects\ha-teamtracker
run_tests.bat
```

### Option B: Quick Test (Manual)
```bash
# Test API connectivity
python quick_test.py

# Test full integration with default team
python test_sofascore.py

# Test with specific team
python test_sofascore.py "Manchester United"
python test_sofascore.py "Barcelona"
python test_sofascore.py "Benfica"

# Test with different sport
python test_sofascore.py "Lakers:basketball"
python test_sofascore.py "Federer:tennis"
```

### Expected Output

✅ **Success looks like:**
```
================================================================================
  SofaScore API Test Script
================================================================================

================================================================================
  TEST 1: Searching for 'Manchester United' in football
================================================================================

  ✅ Found 5 team(s):

  Teams matching sport 'football':

  [1]
  ID:      35
  Name:    Manchester United
  Sport:   Football
  Country: England
  ...
```

❌ **Failure looks like:**
```
❌ 403 Forbidden - Need to update headers
```
If you see 403, the API headers need updating (let me know!)

## 🏠 Step 2: Install to Home Assistant

### Method 1: Manual Installation

1. **Copy files to Home Assistant:**
   ```bash
   # Copy the entire teamtracker folder to your HA config
   Copy from: C:\Users\joao.sousa\PycharmProjects\ha-teamtracker\custom_components\teamtracker
   Copy to: \\<your-ha-server>\config\custom_components\teamtracker
   ```

2. **Restart Home Assistant:**
   - Go to Settings → System → Restart

3. **Add Integration:**
   - Go to Settings → Devices & Services
   - Click "+ Add Integration"
   - Search for "TeamTracker"
   - Fill in:
     - **Team Name**: `Benfica` (or your team)
     - **Sport**: Select `Football (Soccer)` from dropdown
     - **Name**: `benfica` (sensor will be `sensor.benfica`)

4. **Verify it works:**
   - Go to Developer Tools → States
   - Search for `sensor.benfica`
   - Check attributes like `team_name`, `opponent_name`, `date`, etc.

### Method 2: HACS (If you prefer)

*Note: This won't be in official HACS unless you add it as a custom repository*

1. Add custom repository:
   - HACS → Integrations → ⋮ → Custom repositories
   - Add: `https://github.com/<your-fork>/ha-teamtracker`
   - Category: Integration

2. Install and restart

3. Add integration as above

## 📋 Step 3: Verification Checklist

After installation, verify everything works:

- [ ] Integration appears in Settings → Devices & Services
- [ ] Sensor entity is created (check Developer Tools → States)
- [ ] Sensor has attributes:
  - [ ] `team_name`
  - [ ] `opponent_name`
  - [ ] `date`
  - [ ] `state` (PRE/IN/POST/NOT_FOUND)
  - [ ] `league`
  - [ ] `venue`
  - [ ] `kickoff_in`
- [ ] Sensor updates (check `last_update` attribute changes)
- [ ] No errors in logs (Settings → System → Logs)

## 🔍 Troubleshooting

### Team Not Found
```
State: NOT_FOUND
Attribute api_message: "Could not find team 'XYZ' in sport 'football'"
```

**Solutions:**
- Try different name variations:
  - "Man Utd" instead of "Manchester United"
  - "Bayern" instead of "Bayern Munich"
- Check the team name on SofaScore.com
- Make sure sport is correct
- Check logs for exact search query

### No Upcoming Games
```
State: NOT_FOUND
Attribute api_message: "No upcoming event found for this team"
```

**This is normal!**
- Happens during off-season
- Happens if no games are scheduled yet
- Sensor will auto-update when games are scheduled

### 403 Forbidden Errors in Logs
```
SofaScore API returned 403 Forbidden
```

**Solutions:**
- SofaScore may be blocking requests
- Try updating headers in `sofascore_api.py`
- Wait a few minutes and try again
- Check if SofaScore.com is accessible from your network

### Integration Not Showing Up
- Make sure files are in correct location: `config/custom_components/teamtracker/`
- Check that `manifest.json` exists
- Restart Home Assistant
- Check logs for errors during startup

## 🎯 Quick Start Examples

### Example 1: Portuguese Football
```yaml
# Configuration
Team Name: Benfica
Sport: Football (Soccer)
Name: benfica

# Will track Benfica across all competitions:
# - Primeira Liga
# - Taça de Portugal
# - Champions League
# - etc.
```

### Example 2: Multiple Teams
```yaml
# Add multiple sensors for different teams
1. Benfica (Football)
2. Sporting (Football)
3. FC Porto (Football)
4. Lakers (Basketball)
5. Federer (Tennis)
```

### Example 3: Automation
```yaml
automation:
  - alias: "Benfica Game Alert"
    trigger:
      - platform: state
        entity_id: sensor.benfica
        attribute: kickoff_in
        to: "in 1 hour"
    action:
      - service: notify.mobile_app
        data:
          title: "⚽ Benfica"
          message: "Game starts in 1 hour!"

  - alias: "Goal Notification"
    trigger:
      - platform: state
        entity_id: sensor.benfica
        attribute: team_score
    condition:
      - condition: state
        entity_id: sensor.benfica
        attribute: state
        state: "IN"
    action:
      - service: notify.mobile_app
        data:
          title: "⚽ GOAL!"
          message: "Benfica {{ state_attr('sensor.benfica', 'team_score') }} - {{ state_attr('sensor.benfica', 'opponent_score') }} {{ state_attr('sensor.benfica', 'opponent_name') }}"
```

## 📊 Available Sensor Data

Your sensor will have these attributes:

| Attribute | Example | Description |
|-----------|---------|-------------|
| `state` | `IN` | Game status (PRE/IN/POST/NOT_FOUND) |
| `team_name` | `Benfica` | Your team name |
| `team_abbr` | `BEN` | Team abbreviation |
| `team_score` | `2` | Your team's score |
| `team_logo` | `https://...` | Team logo URL |
| `opponent_name` | `Porto` | Opponent name |
| `opponent_score` | `1` | Opponent score |
| `opponent_logo` | `https://...` | Opponent logo |
| `date` | `2025-01-22T20:00:00` | Match date/time |
| `kickoff_in` | `in 2 hours` | Time until kickoff |
| `league` | `Primeira Liga` | League/Competition name |
| `venue` | `Estádio da Luz` | Stadium name |
| `location` | `Lisbon, Portugal` | Match location |
| `quarter` | `2nd Half` | Current period |
| `clock` | `67:32` | Match clock |
| `event_url` | `https://...` | Link to SofaScore match page |

## 🔄 Updating

To update the integration:

1. Replace the `custom_components/teamtracker` folder with new version
2. Restart Home Assistant
3. Existing sensors will continue to work (no reconfiguration needed)

## ❓ Getting Help

1. **Check logs first:**
   - Settings → System → Logs
   - Filter by "teamtracker"

2. **Enable debug logging:**
   ```yaml
   logger:
     default: info
     logs:
       custom_components.teamtracker: debug
   ```

3. **Test locally:**
   - Run `python test_sofascore.py "Your Team"`
   - Check what error you get

4. **Report issues:**
   - Include team name and sport
   - Include relevant log entries
   - Include sensor state/attributes

## ✅ Success!

If everything works, you should see:
- Sensor showing next game information
- Regular updates (every 10 minutes normally, 5 seconds during games)
- No errors in logs

Enjoy tracking your favorite teams! ⚽🏀🎾
