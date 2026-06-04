# WC2026 Footbot — Implementation Plan

## What the original did (2016)

- **3 projects**: football-data.org API client / Slack message builder lib / Flask app gluing them together
- **Slash command**: `/euro fixtures|standings|teams|current|help` → Slack responded with formatted tables
- **Goal push notifications**: football-data.org POSTed to your Flask `/football-data.events` endpoint on every fixture update → you fetched the full fixture, formatted it, and POSTed to a Slack incoming webhook
- **Auth**: `X-Auth-Token` header for football-data.org; plain webhook URL for Slack

---

## What's changed in 10 years

### football-data.org
| | 2016 (v1) | 2026 (v4) |
|---|---|---|
| Base URL | `api.football-data.org/v1/` | `api.football-data.org/v4/` |
| Competition ID | numeric e.g. `398` | string code e.g. `WC` |
| `/soccerseasons/{id}/fixtures` | → | `/competitions/WC/matches` |
| `/soccerseasons/{id}/leagueTable` | → | `/competitions/WC/standings` |
| Push webhooks | Yes (free tier) | **Gone from free tier** |
| Auth header | `X-Auth-Token` | `X-Auth-Token` (unchanged) |
| Rate limit | ~1 req/sec | 10 req/min (free tier) |

**Implication**: No more push webhooks. Goal notifications require **polling** instead.

### Slack API
| | 2016 | 2026 |
|---|---|---|
| Slash commands | Custom integrations (legacy) | Slack App with OAuth |
| Message format | Attachments (deprecated) | **Block Kit** |
| Posting messages | Incoming webhook URL | Incoming webhook (still works) OR Bot token |
| Auth | Webhook URL as secret | OAuth scopes + token |
| Development | Needed public URL | **Socket Mode** (no public URL needed) |

---

## Recommended architecture: single project

```
footbot/
├── main.py                  # entry point: starts Slack app + scheduler
├── config.py                # loads all env vars
├── football_data/
│   ├── client.py            # football-data.org v4 HTTP client
│   └── models.py            # dataclasses for Match, Standing, Team
├── slack/
│   ├── app.py               # Slack Bolt app + slash command handlers
│   └── formatter.py         # football data → Slack Block Kit JSON
├── notifier/
│   └── poller.py            # APScheduler: polls live matches, detects goals
├── .env                     # secrets (not committed)
└── requirements.txt
```

---

## Key libraries

| Library | Purpose |
|---|---|
| `slack-bolt` | Modern Slack SDK: slash commands, posting messages |
| `requests` | HTTP calls to football-data.org |
| `apscheduler` | Background scheduler for live match polling |
| `python-dotenv` | Load `.env` config |
| `dataclasses` / `pydantic` | Typed models for API responses |

```
pip install slack-bolt requests apscheduler python-dotenv pydantic
```

---

## Data flow

### Slash command (`/wc fixtures`)
```
Slack user types /wc fixtures
    → Slack POSTs to your app (via Socket Mode or HTTP)
    → Bolt dispatches to @app.command("/wc")
    → fetch /competitions/WC/matches from football-data.org
    → formatter.py builds Block Kit JSON (table layout)
    → Bolt responds with ack() + message
    → User sees formatted fixture list in Slack
```

### Goal notification (polling)
```
APScheduler: every 60s during match hours
    → fetch /competitions/WC/matches?status=LIVE
    → compare scores against in-memory last-known state
    → if score changed: formatter.py builds goal alert Block Kit message
    → POST to Slack channel via incoming webhook
    → update in-memory state
```

---

## football-data.org v4 endpoints to use

```python
BASE = "https://api.football-data.org/v4"

GET /competitions/WC/matches              # all WC2026 matches (optional ?status=LIVE)
GET /competitions/WC/standings            # group tables
GET /competitions/WC/teams               # all 48 teams
GET /matches/{id}                        # single match detail
```

All requests need header: `X-Auth-Token: <your_token>`

WC2026: 48 teams, 12 groups of 4, tournament June–July 2026.

---

## Slack setup (what you'll need from your Slack admin)

1. **Create a Slack App** at api.slack.com/apps
2. **Enable Socket Mode** (easiest for company Slack — no inbound firewall rules)
3. **Add Bot Token Scopes**:
   - `commands` — to register slash commands
   - `chat:write` — to post messages
   - `incoming-webhook` — to post to a channel
4. **Create slash command** `/wc` pointing to your app
5. **Install to workspace** (needs admin approval if company-managed)

Two tokens to store in `.env`:
- `SLACK_BOT_TOKEN` (xoxb-...)
- `SLACK_APP_TOKEN` (xapp-... for Socket Mode)
- `FOOTBALL_DATA_TOKEN`
- `SLACK_CHANNEL` (channel ID to post goal alerts to)

---

## Slash command design

```
/wc                    → help
/wc fixtures           → all fixtures grouped by status (upcoming / live / finished)
/wc today              → today's matches only
/wc live               → currently in-progress matches with score
/wc table              → group standings
/wc teams              → all 48 teams
/wc group A            → fixtures + table for group A
```

---

## Goal notification design

```python
# In-memory state
live_scores: dict[int, tuple[int, int]] = {}   # match_id → (home_goals, away_goals)

# Polling logic (every 60s when WC is on)
def poll_live_matches():
    matches = client.get_live_matches()
    for match in matches:
        match_id = match.id
        current = (match.score.home, match.score.away)
        previous = live_scores.get(match_id)
        if previous and current != previous:
            # goal scored! figure out who scored
            post_goal_alert(match, previous, current)
        live_scores[match_id] = current
```

---

## Message formatting: Block Kit vs old Attachments

Old (2016):
```python
# Pre-formatted code block with tabs — fragile
"```Date\tHome v Away\n12/06\tEng 1 - 0 Rus```"
```

New (Block Kit): structured, renders beautifully on all clients
```python
{
    "type": "section",
    "text": {"type": "mrkdwn", "text": "*England 1 - 0 Russia*"},
    "fields": [
        {"type": "mrkdwn", "text": "*Scorer*\nWayne Rooney 45'"},
        {"type": "mrkdwn", "text": "*Status*\nFINISHED"}
    ]
}
```

---

## Phased build order

### Phase 1 — football-data.org client
- [ ] `client.py`: authenticated GET wrapper, rate-limit handling
- [ ] `models.py`: Match, Score, Standing, Team dataclasses
- [ ] Test: fetch WC2026 fixtures and print them

### Phase 2 — Slack formatter
- [ ] `formatter.py`: fixtures list, standings table, goal alert → Block Kit JSON
- [ ] Test: print Block Kit JSON to console, paste into Slack Block Kit Builder to preview

### Phase 3 — Slack app + slash commands
- [ ] Set up Slack app (Socket Mode), store tokens in `.env`
- [ ] `app.py`: register `/wc` command, wire to formatter + client
- [ ] Test: type `/wc fixtures` in Slack

### Phase 4 — Goal notifier
- [ ] `poller.py`: APScheduler job, in-memory score state, goal detection
- [ ] Wire goal alerts to post in Slack channel
- [ ] Test: manually mock a score change to verify alert fires

### Phase 5 — Polish
- [ ] Smart scheduling: only poll during match hours (don't burn rate limit)
- [ ] Handle match status transitions (TIMED → IN_PLAY → FINISHED)
- [ ] Handle penalties / extra time scores
- [ ] Error handling / logging

---

## What you need before starting

1. **football-data.org account** — register at football-data.org, get free API token (WC2026 should be included in free tier)
2. **Slack workspace access** — either your own test workspace, or permission from company admin to create an app
3. **Python 3.11+** environment

---

## Risks / open questions

| Question | Detail |
|---|---|
| WC2026 data available? | football-data.org free tier covered Euro 2016; WC2026 should be `competition code = WC` but worth verifying once registered |
| Company Slack approval | Socket Mode means no server needed, which may make admin approval easier |
| Rate limits during live matches | Free tier = 10 req/min; polling every 60s = 1 req/poll, fine |
| Match timezone | football-data.org returns UTC; format output in local time |
