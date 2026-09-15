# Installation & Testing Guide

## 🧪 Step 1: Check it works before installing

Run these from a clone of this repository. They need only `aiohttp` and
`arrow` (`pip install aiohttp arrow`).

```bash
# Does this machine reach SofaScore at all? Run this ON the HA host.
python tests/sofascore/check_connection.py "FC Porto"

# Try any team - by SofaScore id, or by name
python tests/sofascore/try_team.py 3002
python tests/sofascore/try_team.py "FC Porto"

# Which teams are playing right now (gives you ids to try)
python tests/sofascore/try_team.py --live

# Follow a live match, refreshing as the integration does
python tests/sofascore/try_team.py 3002 --watch
```

Success looks like:

```
Resolved 'FC Porto' -> FC Porto (id 3002)
  Competition    Liga Portugal Betclic
  State          PRE
  Kick-off       2026-09-20 19:30 UTC  (5d 6h from now)
```

Failure looks like:

```
SofaScore error: SofaScore refused the request (403 Forbidden)
```

A 403 means SofaScore's edge cache is blocking that host. It is
network-specific, which is why this is worth running on the Home Assistant
machine itself rather than only on your laptop.

## 🏠 Step 2: Install to Home Assistant

### Method 1: Manual Installation

1. **Copy files to Home Assistant:**

   Copy the whole `custom_components/sportsradar/` folder into your Home
   Assistant configuration directory, so you end up with:

   ```
   <ha-config>/custom_components/sportsradar/
       __init__.py
       manifest.json
       sensor.py
       sofascore_api.py
       ...
   ```

   `<ha-config>` is the folder holding `configuration.yaml` - typically
   `/config` on HA OS, or `~/.homeassistant` on a container/core install.
   Create `custom_components/` if it does not exist.

2. **Restart Home Assistant:**
   - Go to Settings → System → Restart

3. **Add Integration:**
   - Go to Settings → Devices & Services
   - Click "+ Add Integration"
   - Search for "SportsRadar"
   - Fill in:
     - **Team/Athlete**: `Benfica` (or your team) - the team
       **name**, which SofaScore searches for; not a numeric id
     - **Sport**: Select `Football (Soccer)` from dropdown
     - **Name**: `benfica` (sensor will be `sensor.benfica`)

4. **Verify it works:**
   - Go to Developer Tools → States
   - Search for `sensor.benfica`
   - Check attributes like `team_name`, `opponent_name`, `date`, etc.

### Method 2: HACS

This repository is **private**, and HACS cannot read a private repository
unless it is given a GitHub token with access to it. For the HACS route,
either make the repository public first, or configure HACS with such a
token. Otherwise use Method 1 - for a single-user setup, copying the folder
is simpler and has no downside.

If the repository is public:

1. HACS -> Integrations -> three-dot menu -> Custom repositories
2. Add `https://github.com/jpcsousa12/ha-sportsradar`, category **Integration**
3. Install, restart Home Assistant, then add the integration as above

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
- Make sure files are in correct location: `config/custom_components/sportsradar/`
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

1. Replace the `custom_components/sportsradar` folder with new version
2. Restart Home Assistant
3. Existing sensors will continue to work (no reconfiguration needed)

## ❓ Getting Help

1. **Check logs first:**
   - Settings → System → Logs
   - Filter by "sportsradar"

2. **Enable debug logging:**
   ```yaml
   logger:
     default: info
     logs:
       custom_components.sportsradar: debug
   ```

3. **Test locally:**
   - Run `python tests/sofascore/try_team.py "Your Team"`
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
