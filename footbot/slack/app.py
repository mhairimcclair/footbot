import logging
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN
from football_data import client
from slack import formatter

logger = logging.getLogger(__name__)

app = App(token=SLACK_BOT_TOKEN)


# ── helpers ───────────────────────────────────────────────────────────────────

def _error_blocks(message: str) -> list[dict]:
    return [{"type": "section", "text": {"type": "mrkdwn", "text": f":warning: {message}"}}]


def _find_team(query: str):
    """Return the first Team whose name or TLA contains query (case-insensitive)."""
    q = query.lower()
    return next(
        (t for t in client.get_teams()
         if q in t.name.lower() or q in t.tla.lower()),
        None,
    )


def _group_combined_blocks(group_letter: str) -> list[dict]:
    key = f"GROUP_{group_letter.upper()}"
    all_matches = client.get_matches()
    group_matches = [m for m in all_matches if m.group == key]
    standings = client.get_standings()

    if not group_matches and not any(g.group == key for g in standings):
        return _error_blocks(f"No data found for Group {group_letter.upper()}. Valid groups are A–L.")

    blocks: list[dict] = []
    if group_matches:
        blocks += formatter.fixtures_blocks(
            group_matches, title=f"WC 2026 — Group {group_letter.upper()} Fixtures"
        )
    if standings:
        blocks += [{"type": "divider"}]
        blocks += formatter.standings_blocks(standings, filter_group=group_letter)
    return blocks[:50]


def _lineup_blocks(query: str) -> list[dict]:
    q = query.lower()
    today = client.get_today_matches()
    match = next(
        (m for m in today
         if q in m.home_team.name.lower() or q in m.home_team.tla.lower()
         or q in m.away_team.name.lower() or q in m.away_team.tla.lower()),
        None,
    )
    if not match:
        all_matches = client.get_matches()
        match = next(
            (m for m in all_matches if m.is_upcoming
             and (q in m.home_team.name.lower() or q in m.home_team.tla.lower()
                  or q in m.away_team.name.lower() or q in m.away_team.tla.lower())),
            None,
        )
    if not match:
        return _error_blocks(f"No match found for *{query}*. Try the team name or TLA (e.g. `scotland`, `sco`).")
    return formatter.lineup_blocks(match)


def _team_blocks(query: str) -> list[dict]:
    team = _find_team(query)
    if not team:
        return _error_blocks(f"Team not found: *{query}*. Try the full name or TLA (e.g. `scotland`, `sco`).")

    detail = client.get_team_detail(team.id)

    # Find this team's standing
    standing = None
    for group in client.get_standings():
        row = next((r for r in group.table if r.team.id == team.id), None)
        if row:
            standing = row
            break

    # Find next upcoming and most recent finished match
    all_matches = client.get_matches()
    team_matches = [
        m for m in all_matches
        if m.home_team.id == team.id or m.away_team.id == team.id
    ]
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    next_match = next(
        (m for m in sorted(team_matches, key=lambda x: x.utc_date)
         if m.is_upcoming and m.utc_date > now),
        None,
    )
    last_match = next(
        (m for m in sorted(team_matches, key=lambda x: x.utc_date, reverse=True)
         if m.is_finished),
        None,
    )

    return formatter.team_blocks(detail, standing, next_match, last_match)


def _h2h_blocks(query1: str, query2: str) -> list[dict]:
    team1 = _find_team(query1)
    team2 = _find_team(query2)

    if not team1:
        return _error_blocks(f"Team not found: *{query1}*")
    if not team2:
        return _error_blocks(f"Team not found: *{query2}*")
    if team1.id == team2.id:
        return _error_blocks("Please provide two different teams.")

    all_matches = client.get_matches()
    standings = client.get_standings()

    def _find_standing(team_id):
        for group in standings:
            row = next((r for r in group.table if r.team.id == team_id), None)
            if row:
                return row
        return None

    return formatter.h2h_blocks(
        team1, team2, all_matches,
        _find_standing(team1.id),
        _find_standing(team2.id),
    )


# ── command handler ───────────────────────────────────────────────────────────

@app.command("/wc")
def handle_wc(ack, respond, command):
    ack()

    text = (command.get("text") or "").strip().lower()
    logger.info("Command /wc %r from %s", text, command.get("user_name"))

    try:
        blocks = _dispatch(text)
    except Exception as e:
        logger.exception("Error handling /wc %r", text)
        blocks = _error_blocks(f"Something went wrong: {e}")

    respond(blocks=blocks, response_type="in_channel")


def _dispatch(text: str) -> list[dict]:
    # /wc group A
    group_match = re.fullmatch(r"group\s+([a-lA-L])", text)
    if group_match:
        return _group_combined_blocks(group_match.group(1))

    # /wc lineup <team>
    lineup_match = re.match(r"lineup\s+(.+)", text)
    if lineup_match:
        return _lineup_blocks(lineup_match.group(1).strip())

    # /wc team <name>
    team_match = re.match(r"team\s+(.+)", text)
    if team_match:
        return _team_blocks(team_match.group(1).strip())

    # /wc h2h <team1> vs <team2>  or  /wc h2h <team1> <team2>
    h2h_vs = re.match(r"h2h\s+(.+?)\s+vs\s+(.+)", text)
    if h2h_vs:
        return _h2h_blocks(h2h_vs.group(1).strip(), h2h_vs.group(2).strip())
    h2h_space = re.match(r"h2h\s+(\S+)\s+(\S+)", text)
    if h2h_space:
        return _h2h_blocks(h2h_space.group(1), h2h_space.group(2))

    dispatch = {
        "fixtures":  lambda: formatter.fixtures_blocks(client.get_matches()),
        "today":     lambda: formatter.today_blocks(client.get_today_matches()),
        "live":      lambda: formatter.live_blocks(client.get_live_matches()),
        "next":      lambda: formatter.next_blocks(client.get_matches()),
        "table":     lambda: formatter.standings_blocks(client.get_standings()),
        "standings": lambda: formatter.standings_blocks(client.get_standings()),
        "top":       lambda: formatter.scorers_blocks(client.get_scorers()),
        "scorers":   lambda: formatter.scorers_blocks(client.get_scorers()),
        "bracket":   lambda: formatter.bracket_blocks(client.get_matches()),
        "teams":     lambda: formatter.teams_blocks(client.get_teams()),
        "help":      lambda: formatter.help_blocks(),
        "":          lambda: formatter.help_blocks(),
    }

    if text not in dispatch:
        return (
            _error_blocks(f"Unknown command: `{text}`")
            + [{"type": "divider"}]
            + formatter.help_blocks()
        )

    return dispatch[text]()


# ── start ─────────────────────────────────────────────────────────────────────

def start():
    logger.info("Starting Footbot in Socket Mode...")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
