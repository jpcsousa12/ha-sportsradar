"""Constants for the Sports Radar integration."""

from datetime import timedelta

from homeassistant.const import Platform

# Config
CONF_API_LANGUAGE = "api_language"
CONF_CONFERENCE_ID = "conference_id"
CONF_LEAGUE_ID = "league_id"
CONF_LEAGUE_PATH = "league_path"
CONF_SPORT_PATH = "sport_path"
CONF_TEAM_ID = "team_id"

# Sports
AUSTRALIAN_FOOTBALL = "australian-football"
BASEBALL = "baseball"
BASKETBALL = "basketball"
CRICKET = "cricket"
FOOTBALL = "football"
GOLF = "golf"
HOCKEY = "hockey"
MMA = "mma"
RACING = "racing"
RUGBY = "rugby"
SOCCER = "soccer"
TENNIS = "tennis"
VOLLEYBALL = "volleyball"

# ESPN-era league ids and their sport/league paths. Still used to validate
# the YAML sensor platform's league_id and to migrate version 1-2 entries.
LEAGUE_MAP = {
    "AFL": {
        CONF_SPORT_PATH: AUSTRALIAN_FOOTBALL,
        CONF_LEAGUE_PATH: "afl",
    },
    "MLB": {
        CONF_SPORT_PATH: BASEBALL,
        CONF_LEAGUE_PATH: "mlb",
    },
    "NBA": {
        CONF_SPORT_PATH: BASKETBALL,
        CONF_LEAGUE_PATH: "nba",
    },
    "WNBA": {
        CONF_SPORT_PATH: BASKETBALL,
        CONF_LEAGUE_PATH: "wnba",
    },
    "NCAAM": {
        CONF_SPORT_PATH: BASKETBALL,
        CONF_LEAGUE_PATH: "mens-college-basketball",
    },
    "NCAAW": {
        CONF_SPORT_PATH: BASKETBALL,
        CONF_LEAGUE_PATH: "womens-college-basketball",
    },
    "NCAAF": {
        CONF_SPORT_PATH: FOOTBALL,
        CONF_LEAGUE_PATH: "college-football",
    },
    "NFL": {
        CONF_SPORT_PATH: FOOTBALL,
        CONF_LEAGUE_PATH: "nfl",
    },
    "XFL": {
        CONF_SPORT_PATH: FOOTBALL,
        CONF_LEAGUE_PATH: "xfl",
    },
    "PGA": {
        CONF_SPORT_PATH: GOLF,
        CONF_LEAGUE_PATH: "pga",
    },
    "NHL": {
        CONF_SPORT_PATH: HOCKEY,
        CONF_LEAGUE_PATH: "nhl",
    },
    "UFC": {
        CONF_SPORT_PATH: MMA,
        CONF_LEAGUE_PATH: "ufc",
    },
    "F1": {
        CONF_SPORT_PATH: RACING,
        CONF_LEAGUE_PATH: "f1",
    },
    "IRL": {
        CONF_SPORT_PATH: RACING,
        CONF_LEAGUE_PATH: "irl",
    },
    "NASCAR": {
        CONF_SPORT_PATH: RACING,
        CONF_LEAGUE_PATH: "nascar-premier",
    },
    "BUND": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "ger.1",
    },
    "CL": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "uefa.champions",
    },
    "CLA": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "conmebol.libertadores",
    },
    "EPL": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "eng.1",
    },
    "LIGA": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "esp.1",
    },
    "LIG1": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "fra.1",
    },
    "MLS": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "usa.1",
    },
    "NWSL": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "usa.nwsl",
    },
    "SERA": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "ita.1",
    },
    "WC": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "fifa.world",
    },
    "WWC": {
        CONF_SPORT_PATH: SOCCER,
        CONF_LEAGUE_PATH: "fifa.wwc",
    },
    "ATP": {
        CONF_SPORT_PATH: TENNIS,
        CONF_LEAGUE_PATH: "atp",
    },
    "WTA": {
        CONF_SPORT_PATH: TENNIS,
        CONF_LEAGUE_PATH: "wta",
    },
    "NCAAVB": {
        CONF_SPORT_PATH: VOLLEYBALL,
        CONF_LEAGUE_PATH: "mens-college-volleyball",
    },
    "NCAAVBW": {
        CONF_SPORT_PATH: VOLLEYBALL,
        CONF_LEAGUE_PATH: "womens-college-volleyball",
    },
}

SPORT_ICON_MAP = {
    AUSTRALIAN_FOOTBALL: "mdi:football-australian",
    BASEBALL: "mdi:baseball",
    BASKETBALL: "mdi:basketball",
    CRICKET: "mdi:cricket",
    FOOTBALL: "mdi:football",
    GOLF: "mdi:golf-tee",
    HOCKEY: "mdi:hockey-puck",
    MMA: "mdi:karate",
    RACING: "mdi:flag-checkered",
    RUGBY: "mdi:rugby",
    SOCCER: "mdi:soccer",
    TENNIS: "mdi:tennis",
    VOLLEYBALL: "mdi:volleyball",
}

# Defaults
DEFAULT_CONFERENCE_ID = ""
# The integration's own identity. Sport-specific icons are still in
# SPORT_ICON_MAP above if you would rather show the sport: swap this
# lookup back in sensor.py.
DEFAULT_ICON = "mdi:radar"
DEFAULT_LEAGUE = ""  # SofaScore finds the competition itself
DEFAULT_NAME = "sports_radar"
DEFAULT_SPORT_PATH = "football"  # Default to football/soccer
DEFAULT_TIMEOUT = 120  # seconds for a whole update
REQUEST_TIMEOUT = 15  # seconds for one SofaScore request
# How long after KICK-OFF a finished match stays on the sensor before it rolls
# over to the next fixture. This is measured from the start of the match, so it
# needs to cover the match itself plus the time the result stays on display.
POST_GAME_HOLD = timedelta(hours=5)

DEFAULT_REFRESH_RATE = timedelta(minutes=10)
RAPID_REFRESH_RATE = timedelta(seconds=5)
# While live, statistics and incidents are refreshed at most this often (in
# seconds); the event itself is still polled at RAPID_REFRESH_RATE.
STATISTICS_MAX_AGE = 60
INCIDENTS_MAX_AGE = 15
# How soon an empty statistics/incidents answer is asked for again.
DETAIL_RETRY_SECONDS = 300
# First retry interval after a failed update; doubles up to the default rate.
FAILURE_BACKOFF = timedelta(seconds=30)

# Services
SERVICE_NAME_CALL_API = "call_api"
SERVICE_NAME_DIAGNOSE = "diagnose"

# Misc
VERSION = "v1.4.1"
ISSUE_URL = "https://github.com/jpcsousa12/ha-sportsradar"
DOMAIN = "sportsradar"
ATTRIBUTION = "Data provided by SofaScore"
COORDINATOR = "coordinator"
PLATFORMS = [Platform.SENSOR]

# Sport options for configuration
SPORT_OPTIONS = [
    ("football", "Football (Soccer)"),
    ("basketball", "Basketball"),
    ("tennis", "Tennis"),
    ("hockey", "Ice Hockey"),
    ("american-football", "American Football"),
    ("baseball", "Baseball"),
    ("volleyball", "Volleyball"),
    ("handball", "Handball"),
    ("rugby", "Rugby"),
    ("cricket", "Cricket"),
    ("mma", "MMA"),
    ("motorsport", "Motorsport"),
]
