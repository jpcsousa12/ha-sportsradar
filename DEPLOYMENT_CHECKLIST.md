# Deployment Checklist - Sports Radar (SofaScore Edition)

## ✅ Pre-Deployment Verification

### Code Quality
- [x] All ESPN legacy code moved to `_espn_legacy/` folder
- [x] Only SofaScore files in main integration folder
- [x] No test files in integration folder
- [x] manifest.json updated to version 0.15.0
- [x] All imports reference SofaScore modules only

### Integration Structure
```
custom_components/sportsradar/
├── __init__.py                 ✅ SofaScore coordinator
├── sensor.py                   ✅ Sensor entity
├── config_flow.py              ✅ Team-based configuration
├── const.py                    ✅ SofaScore constants
├── manifest.json               ✅ v0.15.0
├── sofascore_api.py            ✅ API client with live detection
├── sofascore_processor.py      ✅ Event processor
├── clear_values.py             ✅ Value clearer
└── translations/               ✅ UI strings
```

### Functionality Tests
- [x] Team search works (tested: FC Porto, La Serena)
- [x] Live game detection works (Code: 6, 7, 31, etc.)
- [x] Next game detection works
- [x] State changes: PRE → IN → POST
- [x] Live statistics fetching works
- [x] Rapid refresh during games (5 seconds)
- [x] Normal refresh when idle (10 minutes)

## 🚀 Deployment Steps

### 1. Backup Current Installation (if upgrading)
```bash
# If you have existing SportsRadar installed
cp -r /config/custom_components/sportsradar /config/custom_components/sportsradar.backup
```

### 2. Install Integration
```bash
# Copy integration folder to Home Assistant
cp -r custom_components/sportsradar /config/custom_components/
```

### 3. Restart Home Assistant
- Settings → System → Restart
- Wait for restart to complete

### 4. Add Integration
- Settings → Devices & Services
- Click "+ Add Integration"
- Search: "Sports Radar"
- Fill in:
  - **Team Name**: e.g., "FC Porto", "Benfica", "Manchester United"
  - **Sport**: Select from dropdown
  - **Name** (optional): Sensor name

### 5. Verify Installation
- Developer Tools → States
- Find your sensor: `sensor.<your_team_name>`
- Check attributes:
  - ✅ `team_name` populated
  - ✅ `opponent_name` populated (or NOT_FOUND if no game)
  - ✅ `state` shows PRE/IN/POST/NOT_FOUND
  - ✅ `date` shows next game date
  - ✅ `league` shows competition name

### 6. Test Live Game Detection
**Wait for a game to start**, or test with a team currently playing:
- State should change to `IN`
- `team_score` and `opponent_score` should update
- `clock` should show game time
- Updates every 5 seconds during game

## 🔍 Troubleshooting

### Integration Not Showing Up
**Problem**: SportsRadar not in integration list
**Solution**:
1. Check files are in `/config/custom_components/sportsradar/`
2. Check `manifest.json` exists and is valid JSON
3. Check Home Assistant logs for errors
4. Restart Home Assistant again

### Team Not Found
**Problem**: "Could not find team 'XYZ'"
**Solution**:
1. Try different name variations:
   - "Man United" vs "Manchester United"
   - "Bayern" vs "Bayern Munich"
2. Check team name on SofaScore.com
3. Make sure sport is correct
4. Check logs for actual search query

### No Live Game Detected
**Problem**: Game is live but showing as "PRE"
**Solution**:
1. Check if game is on SofaScore.com
2. Check sensor `last_update` - should update every 5 seconds during game
3. Check logs for "LIVE event" messages
4. Verify sport parameter is correct ('football' not 'soccer')

### API Errors
**Problem**: "SofaScore API Error" or 403 Forbidden
**Solution**:
1. Check internet connection
2. Check SofaScore.com is accessible
3. Wait a few minutes (temporary block)
4. Check logs for specific error message

## 📊 Expected Behavior

### Before Game (PRE)
- `state`: PRE
- `kickoff_in`: "in X hours/days"
- `team_score`: 0
- `opponent_score`: 0
- Updates: Every 10 minutes
- Rapid updates start: 20 minutes before kickoff

### During Game (IN)
- `state`: IN
- `kickoff_in`: "Started"
- `team_score`: Live score
- `opponent_score`: Live score
- `clock`: Game time
- `quarter`: Period/Half
- Statistics: Possession, shots, etc.
- Updates: Every 5 seconds

### After Game (POST)
- `state`: POST
- `team_score`: Final score
- `opponent_score`: Final score
- `team_winner`: true/false
- Updates: Back to 10 minutes

### No Game (NOT_FOUND)
- `state`: NOT_FOUND
- `api_message`: "No upcoming event"
- Normal during off-season
- Updates: Every 10 minutes

## 🎯 Performance

### API Usage
- **Normal**: 1 request / 10 minutes = ~144 requests/day
- **During game**: 1 request / 5 seconds = 720 requests/hour
- **Daily estimate**: ~200-300 requests (depending on game length)
- **SofaScore limits**: None (unofficial API, be respectful)

### Resource Usage
- **Memory**: <5 MB per sensor
- **CPU**: Minimal (<1%)
- **Network**: ~1-2 KB per request

## ⚠️ Important Notes

### 1. Unofficial API
- Uses SofaScore's unofficial API
- Not affiliated with or endorsed by SofaScore
- API structure may change without notice
- Use responsibly

### 2. Rate Limiting
- Integration implements smart caching
- Respects SofaScore servers
- Uses proper User-Agent headers
- Follows rate limiting best practices

### 3. Data Accuracy
- Data sourced directly from SofaScore
- Same data as SofaScore website/app
- Updates in near real-time during games
- Minor delays possible (5-10 seconds)

### 4. Sport Coverage
Currently optimized for:
- ✅ Football (Soccer) - Fully tested
- ⚠️  Basketball - Basic support
- ⚠️  Tennis - Basic support
- ⚠️  Other sports - Basic support

## 🆘 Getting Help

1. **Check Logs**:
   ```
   Settings → System → Logs
   Filter: "sportsradar"
   ```

2. **Enable Debug Logging**:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.sportsradar: debug
   ```

3. **Test Locally** (before deploying):
   ```bash
   cd ha-sportsradar
   python tests/sofascore/quick_test_simple.py
   python tests/sofascore/test_sofascore.py "Your Team"
   ```

4. **Report Issues**:
   - Include team name and sport
   - Include relevant log entries
   - Include sensor state/attributes
   - Include what you expected vs what happened

## ✅ Ready for Production?

### YES, if:
- [x] You tested with at least one team
- [x] Live game detection works
- [x] You're okay with unofficial API usage
- [x] You understand potential changes to API

### NO, wait if:
- [ ] You haven't tested locally
- [ ] You need guaranteed API stability
- [ ] You need official support
- [ ] You need all sports equally supported

## 🎉 Deployment Complete!

If all checks passed:
1. Integration is installed ✅
2. Sensor is created ✅
3. Data is updating ✅
4. Live games work ✅

**Enjoy tracking your favorite teams!** ⚽🏀🎾

---

**Version**: 0.15.0
**API**: SofaScore (Unofficial)
**Last Updated**: 2025-01-22
