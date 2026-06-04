from dotenv import load_dotenv
import os

load_dotenv()

FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]

WC_COMPETITION = "WC"
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"

# Set FOOTBALL_DATA_TIER=paid in .env after upgrading your subscription.
# free: 10 req/min → 6.5s between requests, 60s poll interval
# paid: 30 req/min → 2.0s between requests, 30s poll interval
_tier = os.getenv("FOOTBALL_DATA_TIER", "free").lower()
FOOTBALL_DATA_MIN_INTERVAL = 2.0 if _tier == "paid" else 6.5
FOOTBALL_DATA_POLL_INTERVAL = 30 if _tier == "paid" else 60

# Matchday summary fires daily at this UTC time (default 05:00 — covers late American kick-offs)
MATCHDAY_SUMMARY_HOUR   = int(os.getenv("MATCHDAY_SUMMARY_HOUR", 5))
MATCHDAY_SUMMARY_MINUTE = int(os.getenv("MATCHDAY_SUMMARY_MINUTE", 0))
