# TeamTracker - SofaScore Edition

> **Fork notice.** This project is derived from
> [vasqued2/ha-teamtracker](https://github.com/vasqued2/ha-teamtracker) and is
> licensed under the **GNU General Public License v3.0** (see [LICENSE](LICENSE)),
> the same licence as the upstream project. Copyright in the original work
> remains with its authors.
>
> The data source has been changed from ESPN to **SofaScore**. Despite the
> repository name, this integration does **not** use Sportradar.

## 🔄 Major Update: ESPN → SofaScore Migration

This is a modified version of ha-teamtracker that uses **SofaScore** instead of ESPN as the data source.

### Why SofaScore?

- ✅ **Completely Free** - No API limits or rate restrictions
- ✅ **All Leagues** - Track any team across all competitions without specifying leagues
- ✅ **Global Coverage** - Better international sports coverage
- ✅ **Live Updates** - Real-time match statistics and events
- ✅ **No Configuration Complexity** - Simply enter team name and sport

### Key Differences from Original

| Feature | ESPN Version | SofaScore Version |
|---------|--------------|-------------------|
| Data Source | ESPN API | SofaScore API |
| Configuration | League + Team ID | Team Name + Sport |
| League Support | Pre-configured leagues | All leagues automatically |
| API Limits | None (unofficial) | None (unofficial) |
| International Coverage | Limited | Comprehensive |
| Setup Complexity | Medium | Simple |

## 🚀 Quick Start

### Installation

1. Copy the `custom_components/teamtracker` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Configuration** → **Integrations** → **Add Integration**
4. Search for "TeamTracker"

### Configuration

The setup is now much simpler:

1. **Team Name**: Enter the team name (e.g., "Manchester United", "Barcelona", "Lakers")
2. **Sport**: Select from dropdown (Football/Soccer, Basketball, Tennis, etc.)
3. **Name** (optional): Friendly name for your sensor

That's it! No need to specify leagues, conferences, or team IDs.

## 📖 How It Works

### Team Search

When you configure a sensor, TeamTracker will:
1. Search SofaScore for your team name in the selected sport
2. Cache the team ID for faster subsequent updates
3. Automatically fetch the next upcoming game for that team

### Updates

- **Default**: Updates every 10 minutes
- **Live Games**: Updates every 5 seconds during active games
- **Pre-Game**: Updates every 5 seconds within 20 minutes of kickoff

## 🏆 Supported Sports

- ⚽ **Football (Soccer)** - All leagues worldwide
- 🏀 **Basketball** - NBA, Euroleague, etc.
- 🎾 **Tennis** - ATP, WTA, Grand Slams
- 🏒 **Ice Hockey** - NHL, KHL, etc.
- 🏈 **American Football** - NFL, College
- ⚾ **Baseball** - MLB, NPB, etc.
- 🏐 **Volleyball** - All leagues
- 🤾 **Handball** - All leagues
- 🏉 **Rugby** - Union and League
- 🏏 **Cricket** - International and domestic
- 🥊 **MMA** - UFC and others
- 🏎️ **Motorsport** - F1, MotoGP, etc.

## 📊 Available Data

The sensor provides extensive data for each game:

### Basic Information
- Team names, logos, and colors
- Opponent information
- Match date and time
- Countdown to kickoff
- Venue and location

### Live Game Data
- Current score
- Match status (PRE, IN, POST)
- Clock/Time
- Period/Quarter/Half

### Statistics (when available)
- Shots on target
- Total shots
- Ball possession
- Win probability

### URLs
- Direct link to match on SofaScore
- Team logos
- League logos

## 🔧 Advanced Usage

### Service: teamtracker.call_api

Dynamically change what team/sport a sensor is tracking:

```yaml
service: teamtracker.call_api
data:
  sport_path: "football"
  league_path: ""  # Not used in SofaScore mode
  team_id: "Real Madrid"
  entity_id: sensor.team_tracker
```

### Automation Example

Track your favorite team and get notifications:

```yaml
automation:
  - alias: "Game Starting Soon"
    trigger:
      - platform: state
        entity_id: sensor.my_team
        attribute: state
        to: "PRE"
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.my_team', 'kickoff_in') == 'in 30 minutes' }}"
    action:
      - service: notify.mobile_app
        data:
          message: "{{ state_attr('sensor.my_team', 'team_name') }} plays in 30 minutes!"

  - alias: "Goal Scored"
    trigger:
      - platform: state
        entity_id: sensor.my_team
        attribute: team_score
    condition:
      - condition: state
        entity_id: sensor.my_team
        attribute: state
        state: "IN"
    action:
      - service: notify.mobile_app
        data:
          message: "GOAL! {{ state_attr('sensor.my_team', 'team_score') }} - {{ state_attr('sensor.my_team', 'opponent_score') }}"
```

## 🎨 Display Card

This integration works great with the **ha-teamtracker-card** for visual display:

```yaml
type: custom:teamtracker-card
entity: sensor.my_team
```

## 🐛 Troubleshooting

### Team Not Found

If your team isn't found:
- Try different name variations (e.g., "Man United" vs "Manchester United")
- Make sure you selected the correct sport
- Check the logs for the exact search being performed

### No Upcoming Games

- The sensor will show "NOT_FOUND" if there are no scheduled games
- This is normal during off-season
- The sensor will automatically update when games are scheduled

### Statistics Not Showing

- Statistics are only available during live games
- Some sports may have limited statistics
- Check the SofaScore website to see what data is available

## 📝 Known Limitations

1. **Unofficial API**: SofaScore doesn't provide an official API. While this version uses proper headers and respectful request patterns, there's always a small risk of blocks or changes.

2. **Historical Data**: Only shows next upcoming game, not past games (use the SofaScore API's "last event" endpoint if needed).

3. **Multiple Games**: If a team has multiple games on the same day, only the next one is shown.

4. **Statistics Availability**: Not all sports/leagues provide the same level of detail.

## 🔒 Privacy & Ethics

- This integration uses SofaScore's unofficial API
- Requests include proper User-Agent headers
- Rate limiting is implemented (5s for live games, 10min otherwise)
- No personal data is collected or transmitted
- All data requests are read-only

## 🤝 Contributing

Found a bug or want to add a feature?
1. Open an issue describing the problem/feature
2. Submit a pull request with your changes
3. Ensure all existing functionality still works

## 📜 License

This project maintains the same license as the original ha-teamtracker.

## 🙏 Credits

- Original **ha-teamtracker** by @vasqued2
- Original **ha-nfl** by @zacs
- SofaScore for providing comprehensive sports data
- Home Assistant community

## ⚠️ Disclaimer

This is an unofficial integration using SofaScore's API. It is not affiliated with, endorsed by, or connected to SofaScore or its parent companies. Use at your own discretion.

## 📞 Support

- **Issues**: GitHub Issues
- **Questions**: GitHub Discussions
- **Original Project**: [ha-teamtracker](https://github.com/vasqued2/ha-teamtracker)

---

**Version**: 0.15.0-sofascore
**Last Updated**: 2025-01-22
