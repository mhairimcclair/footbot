# WC2026 Footbot

**GitHub:** https://github.com/mhairimcclair/footbot

A Slack bot for World Cup 2026 (11 Jun – 19 Jul 2026). Posts live goal alerts, red cards, and line-ups to a Slack channel, and responds to slash commands for fixtures, standings, and more.

This came from a Slack bot I wrote back in 2016 for Euro 2016, using the same football-data.org API. That API and the Slack one have obviously changed since 2016, and so I used Claude to update these + make major improvements to the original cobbled-together code.

---

## Features

**Automatic notifications** (posted to your channel as they happen):
- ⚽ Goal alerts — scorer name, minute, assist, own goals and penalties labelled (paid tier)
- 🔄 Substitution alerts
- 🟥 Red card / second yellow alerts
- 📋 Line-ups posted when they become available (~60 min before kick-off)
- 🟢 Kick off / ⏸️ Half time / ✅ Full time
- ⏱️ Extra time and 🎯 Penalty shootout alerts
- 📊 End-of-day matchday summary (posted at 05:00 UTC)
- 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Totally unbiased team-specific easter eggs

**Slash commands** (`/wc <subcommand>`):

| Command | Description |
|---|---|
| `/wc fixtures` | All fixtures grouped by date |
| `/wc today` | Today's matches |
| `/wc next` | Next 3 upcoming matches |
| `/wc live` | Matches currently in progress |
| `/wc table` | All group standings |
| `/wc group A` | Fixtures + table for one group (A–L) |
| `/wc team scotland` | Squad, coach, standing & next match |
| `/wc lineup scotland` | Starting XI for a team |
| `/wc top` | Golden Boot leaderboard |
| `/wc h2h scotland england` | Head to head between two teams |
| `/wc bracket` | Knockout stage bracket |
| `/wc teams` | All 48 teams |
| `/wc help` | Show all commands |

---

## Setup

### 1. football-data.org

Register at [football-data.org](https://www.football-data.org/client/register) and copy your API token. The free tier (10 req/min) covers fixtures, standings, and live scores. Upgrade to the paid tier (30 req/min) to unlock goal scorers, bookings, substitutions, and line-ups.

### 2. Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. **Socket Mode** → enable → create an App-Level Token with scope `connections:write` → copy the `xapp-…` token
3. **OAuth & Permissions** → Bot Token Scopes → add `commands`, `chat:write` → **Install to Workspace** → copy the `xoxb-…` token
4. **Slash Commands** → create `/wc` (Request URL can be anything — Socket Mode ignores it)
5. Invite the bot to your channel: `/invite @Footbot`

Your `SLACK_CHANNEL` is the channel ID — right-click the channel → **Copy link**, it's the last segment of the URL (e.g. `C0123456789`).

### 3. Install dependencies

Requires Python 3.9+.

```bash
cd footbot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
FOOTBALL_DATA_TOKEN=your_token_here
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_APP_TOKEN=xapp-your-token-here
SLACK_CHANNEL=C0123456789
FOOTBALL_DATA_TIER=free        # change to "paid" after upgrading

# End-of-day matchday summary time (UTC). Default 05:00 covers late
# West Coast kick-offs for WC2026 in the Americas.
MATCHDAY_SUMMARY_HOUR=5
MATCHDAY_SUMMARY_MINUTE=0
```

---

## Running

```bash
cd footbot
.venv/bin/python main.py
```

The bot connects to Slack via Socket Mode and starts polling for live matches in the background. No public URL or open ports required.

---

## Project structure

```
footbot/
├── main.py                  # Entry point
├── config.py                # Loads .env
├── easter_eggs.py           # Team-specific easter eggs (totally unbiased)
├── requirements.txt
├── .env.example
│
├── football_data/
│   ├── client.py            # football-data.org v4 API client (rate-limited, cached)
│   ├── models.py            # Match, Score, Goal, Booking, Lineup, Substitution,
│   │                        # TeamDetail, Scorer dataclasses
│   └── cache.py             # Thread-safe TTL cache (30s–1hr per endpoint)
│
├── slack/
│   ├── app.py               # Slack Bolt app + /wc command handler
│   └── formatter.py         # football data → Slack Block Kit JSON
│
└── notifier/
    └── poller.py            # APScheduler: polls today's matches, fires alerts
```

---

## API rate limits & polling

| Tier | Requests/min | Poll interval | Cache TTLs |
|---|---|---|---|
| Free | 10 | 60s | live: 30s, today: 90s, fixtures/standings: 5min, teams: 1hr |
| Paid | 30 | 30s | same |

The poller skips API calls when no matches are active or starting within 2 hours, conserving quota on quiet days.

---

## Testing

```bash
# Simulate a full match lifecycle (no API or Slack needed)
.venv/bin/python test_poller.py

# Verify the football-data.org API client
.venv/bin/python test_client.py

# Preview Block Kit message formatting
.venv/bin/python test_formatter.py

# Post real test messages to your Slack channel
.venv/bin/python test_slack_post.py
```
