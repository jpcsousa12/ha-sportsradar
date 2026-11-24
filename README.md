<p align="center">
  <img src="custom_components/sportsradar/brand/logo.png" alt="Sports Radar" width="440">
</p>

<h1 align="center">Sports Radar</h1>

<p align="center">
  Home Assistant sensor that follows a team's matches, with data from SofaScore.
</p>

<p align="center">
  <a href="https://github.com/jpcsousa12/ha-sportsradar/releases/latest"><img src="https://img.shields.io/github/v/release/jpcsousa12/ha-sportsradar" alt="Latest release"></a>
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/jpcsousa12/ha-sportsradar" alt="License"></a>
</p>

> **Fork notice.** Derived from
> [vasqued2/ha-teamtracker](https://github.com/vasqued2/ha-teamtracker) and
> licensed under the **GNU General Public License v3.0** (see [LICENSE](LICENSE)),
> like the upstream project. Copyright in the original work remains with its
> authors. The data source was changed from ESPN to **SofaScore**. Despite the
> name, this integration does **not** use Sportradar.

## What it does

You give it a team name and a sport. It creates a sensor that follows that
team's current or next match in any competition (league, cup, Champions
League...), so there is no league to pick.

| Sensor state | Meaning |
|---|---|
| `PRE` | Next match is scheduled |
| `IN` | Match in progress |
| `POST` | Match over (kept for a few hours, then the next fixture takes over) |
| `NOT_FOUND` | No match found for the team |

The sensor refreshes every 10 minutes, and every 5 seconds from 20 minutes
before kickoff until the match ends (including a late kickoff).

## Installation

Requires Home Assistant 2024.1 or later. The integration icon and logo show
from Home Assistant 2026.3.

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/jpcsousa12/ha-sportsradar`, type **Integration**
3. Install **Sports Radar** and restart Home Assistant

### Manual

Copy `custom_components/sportsradar/` into `<config>/custom_components/` and
restart Home Assistant.

## Configuration

**Settings → Devices & services → Add integration → Sports Radar**

- **Team**: the team name (e.g. `FC Porto`, `Real Madrid`), or its SofaScore
  numeric id (the number at the end of the team's SofaScore URL, e.g. `3002`)
- **Sport**: Football, Basketball, Tennis, Ice Hockey, American Football,
  Baseball, Volleyball, Handball, Rugby, Cricket, MMA or Motorsport
- **Name** (optional): name for the sensor

Football is the best covered sport. Other sports get the score and match
state; most extra attributes below are football only.

## Attributes

### Match
| Attribute | Example |
|---|---|
| `event_name` | `Feyenoord - FC Porto` |
| `league`, `league_logo` | `UEFA Champions League` |
| `season` | `UEFA Champions League 26/27` |
| `date`, `kickoff_in` | `2026-11-24T20:00:00+00:00`, `in 2 days` |
| `venue`, `location` | `De Kuip`, `Rotterdam, Netherlands` |
| `quarter` | Current period: `1st half`, `Halftime`, `2nd half`, `Ended` |
| `clock` | Live minute: `34'`, `45+2'` |
| `last_play` | `22' Yellow card: Alberto Costa (FC Porto)` |
| `event_url` | Link to the match on SofaScore |

### Teams
Each of these exists as `team_*` (the tracked team) and `opponent_*`.

| Attribute | Example |
|---|---|
| `*_name`, `*_long_name`, `*_abbr` | `FC Porto`, `FCP` |
| `*_id`, `*_url`, `*_logo` | SofaScore id, team page and logo |
| `*_homeaway` | `home` / `away` |
| `*_score` | `1` |
| `*_winner` | `true` / `false` once the match is over |
| `*_colors` | Club colours: `["#194f93", "#ffffff"]` |
| `*_kit_colors` | Shirt worn in this match (shirt, number, outline): `["#c2e5e9", "#0477de", "#c2e5e9"]` |
| `*_goalkeeper_colors` | Goalkeeper shirt, same format |
| `*_formation` | `4-3-3` |

`*_kit_colors`, `*_goalkeeper_colors` and `*_formation` come from the line-ups,
so they appear once SofaScore publishes them, usually about an hour before
kickoff. Unlike `*_colors`, they reflect away and third kits.

### Match statistics (football)
`possession`, `team_total_shots`, `team_shots_on_target`, `team_corners`,
`team_yellow_cards`, `team_red_cards`, `team_xg`, and the same for
`opponent_*`. Updated during the match and kept at their final values after
full time.

Attributes kept from ha-teamtracker for compatibility but not provided by
SofaScore (`odds`, `tv_network`, `*_rank`, `*_record`, `*_win_probability`,
baseball and American football fields) stay empty.

## Services

### `sportsradar.call_api`
Point a sensor at another team without reconfiguring it:

```yaml
action: sportsradar.call_api
target:
  entity_id: sensor.sports_radar
data:
  sport_path: football
  team_id: Real Madrid  # or the SofaScore numeric id
```

### `sportsradar.diagnose`
If the sensor is unavailable with a 403 error, this tries several connection
settings against SofaScore from your Home Assistant host and writes the results
to the log.

## Automation example

```yaml
automation:
  - alias: "Goal for my team"
    triggers:
      - trigger: state
        entity_id: sensor.sports_radar
        attribute: team_score
    conditions:
      - condition: state
        entity_id: sensor.sports_radar
        state: "IN"
    actions:
      - action: notify.mobile_app
        data:
          message: >-
            GOAL! {{ state_attr('sensor.sports_radar', 'team_name') }}
            {{ state_attr('sensor.sports_radar', 'team_score') }}-{{ state_attr('sensor.sports_radar', 'opponent_score') }}
```

## Troubleshooting

- **Team not found**: try another spelling, or use the SofaScore numeric id,
  and check the sport.
- **Sensor unavailable / 403**: SofaScore sometimes blocks particular networks.
  Run the `sportsradar.diagnose` service and check the log. From a clone of this
  repository you can also test the connection on the Home Assistant host with
  `python tests/sofascore/check_connection.py "FC Porto"` (needs `aiohttp` and
  `arrow`).
- **Kit colours empty**: line-ups are not out yet, or SofaScore has none for
  that competition.

To see what the integration is doing, enable debug logging in
`configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.sportsradar: debug
```

### Check before installing

From a clone of this repository (needs `aiohttp` and `arrow`), `try_team.py`
runs the integration's own API client and processor and prints what the sensor
would show:

```bash
python tests/sofascore/try_team.py "FC Porto"       # by name or SofaScore id
python tests/sofascore/try_team.py --live           # teams playing right now
python tests/sofascore/try_team.py "FC Porto" --watch   # follow a live match
```

A 403 means SofaScore is blocking that network. It is network-specific, so run
the check on the Home Assistant host, not only on your laptop.

## Limitations

- SofaScore has no official public API. This integration uses the same
  endpoints as their website, which can change or be blocked without notice.
- Only one match per sensor: the one in progress, otherwise the next one.

## Development

```bash
pip install -r requirements_test.txt pylint pillow
python -m pytest                       # Home Assistant tests
python tests/sofascore/test_logic.py   # offline SofaScore checks
pylint custom_components/sportsradar tests scripts
```

CI runs pytest with coverage (Python 3.12 and 3.13), pylint (Python 3.13),
hassfest and the HACS action on every push.

## Credits

- [ha-teamtracker](https://github.com/vasqued2/ha-teamtracker) by vasqued2, which this project is built on
- [SofaScore](https://www.sofascore.com) for the data

## Disclaimer

Unofficial integration, not affiliated with or endorsed by SofaScore or
Sportradar.
