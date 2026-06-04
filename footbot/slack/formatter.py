"""
Converts football_data models into Slack Block Kit message payloads.

Each public function returns a list of Block Kit block dicts, ready to pass
directly to Slack's `blocks=` parameter.

Slack limits: 50 blocks per message, 3000 chars per text element.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from football_data.models import (
    Match, StandingGroup, Team, Goal, Booking, Lineup,
    Substitution, TeamDetail, Scorer, TableRow,
)
import easter_eggs

# ── Status display ────────────────────────────────────────────────────────────

_STATUS_EMOJI = {
    "SCHEDULED": "⏳",
    "TIMED":     "⏰",
    "IN_PLAY":   "🟢",
    "PAUSED":    "⏸️",
    "FINISHED":  "✅",
    "POSTPONED": "⚠️",
    "CANCELLED": "❌",
    "SUSPENDED": "⚠️",
    "AWARDED":   "🏆",
}


def _status_label(match: Match) -> str:
    emoji = _STATUS_EMOJI.get(match.status, "❓")
    if match.status == "IN_PLAY":
        return f"{emoji} LIVE"
    if match.status == "PAUSED":
        return f"{emoji} HT"
    if match.is_finished:
        return f"{emoji} FT"
    if match.status in ("POSTPONED", "CANCELLED", "SUSPENDED"):
        return f"{emoji} {match.status}"
    return f"{emoji} {match.utc_date.strftime('%d %b, %H:%M')} UTC"


def _match_line(match: Match) -> str:
    """Single line representation of a match for use inside a section block."""
    home = match.home_team.tla or match.home_team.name
    away = match.away_team.tla or match.away_team.name
    status = _status_label(match)
    if match.is_live or match.is_finished or match.status == "PAUSED":
        score = match.score.display()
        return f"*{home}* {score} *{away}*  ·  {status}"
    return f"*{home}* vs *{away}*  ·  {status}"


def _group_label(raw: Optional[str]) -> str:
    """'GROUP_A' → 'Group A',  None → ''"""
    if not raw:
        return ""
    return raw.replace("GROUP_", "Group ").replace("_", " ").title()


def _stage_label(raw: str) -> str:
    return raw.replace("_", " ").title()


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text}}


def _divider() -> dict:
    return {"type": "divider"}


def _context(*parts: str) -> dict:
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "  ·  ".join(p for p in parts if p)}],
    }


# ── Public formatters ─────────────────────────────────────────────────────────

def fixtures_blocks(matches: list[Match], title: str = "WC 2026 — Fixtures") -> list[dict]:
    """
    Fixtures grouped by date.  Pass any filtered list of matches —
    the slash command handler decides which matches to include.
    Capped at 45 blocks to stay within Slack's 50-block limit.
    """
    blocks: list[dict] = [_header(f"🏆  {title}")]

    by_date: dict = defaultdict(list)
    for m in sorted(matches, key=lambda m: m.utc_date):
        by_date[m.utc_date.strftime("%A  %d %B")].append(m)

    for date_label, day_matches in by_date.items():
        if len(blocks) >= 45:
            blocks.append(_section("_… more matches not shown — try `/wc today` or `/wc group <X>`_"))
            break
        blocks.append(_divider())
        blocks.append(_section(f"*{date_label}*"))
        lines = [_match_line(m) for m in day_matches]
        blocks.append(_section("\n".join(lines)))

    return blocks


def next_blocks(matches: list[Match], count: int = 3) -> list[dict]:
    """Next N upcoming matches across the whole tournament."""
    now = datetime.now(tz=timezone.utc)
    upcoming = sorted(
        [m for m in matches if m.is_upcoming and m.utc_date > now],
        key=lambda m: m.utc_date,
    )[:count]

    if not upcoming:
        return [
            _header("🏆  WC 2026 — Next Matches"),
            _section("No upcoming matches found."),
        ]

    blocks: list[dict] = [_header(f"🏆  WC 2026 — Next {len(upcoming)} Matches")]
    for m in upcoming:
        group = _group_label(m.group) or _stage_label(m.stage)
        blocks.append(_divider())
        blocks.append(_section(
            f"*{m.home_team.name}* vs *{m.away_team.name}*\n"
            f"⏰ {m.utc_date.strftime('%A %d %B, %H:%M UTC')}  ·  {group}"
        ))
    return blocks


def today_blocks(matches: list[Match]) -> list[dict]:
    if not matches:
        return [
            _header("🏆  WC 2026 — Today"),
            _section("No matches scheduled for today."),
        ]
    return fixtures_blocks(matches, title="WC 2026 — Today's Matches")


def live_blocks(matches: list[Match]) -> list[dict]:
    if not matches:
        return [
            _header("🏆  WC 2026 — Live"),
            _section("No matches in progress right now."),
        ]

    blocks: list[dict] = [_header("🟢  WC 2026 — Live Now")]
    for m in matches:
        score = m.score.display()
        group = _group_label(m.group) or _stage_label(m.stage)
        blocks.append(_divider())
        blocks.append(_section(
            f"*{m.home_team.name}*  {score}  *{m.away_team.name}*"
        ))
        if m.score.home_half is not None:
            ht = f"HT: {m.score.home_half} - {m.score.away_half}"
            blocks.append(_context(group, ht))
        else:
            blocks.append(_context(group))

    return blocks


def standings_blocks(groups: list[StandingGroup], filter_group: Optional[str] = None) -> list[dict]:
    """
    Full group standings table, or a single group if filter_group is given (e.g. 'A').
    Uses a monospace code block for column alignment.
    """
    blocks: list[dict] = [_header("🏆  WC 2026 — Group Standings")]

    target = groups
    if filter_group:
        key = f"GROUP_{filter_group.upper()}"
        target = [g for g in groups if g.group == key]
        if not target:
            blocks.append(_section(f"No standings found for Group {filter_group.upper()}."))
            return blocks

    for grp in target:
        letter = grp.group.replace("GROUP_", "")
        header_line = f"{'Pos':<4} {'Team':<22} {'P':>2} {'W':>2} {'D':>2} {'L':>2} {'GD':>4} {'Pts':>4}"
        separator   = "-" * len(header_line)
        rows = [header_line, separator]
        for row in grp.table:
            name = (row.team.short_name or row.team.name)[:20]
            rows.append(
                f"{row.position:<4} {name:<22} {row.played:>2} {row.won:>2} "
                f"{row.draw:>2} {row.lost:>2} {row.goal_difference:>+4} {row.points:>4}"
            )
        table_text = "```" + "\n".join(rows) + "```"

        blocks.append(_divider())
        blocks.append(_section(f"*Group {letter}*\n{table_text}"))

        if len(blocks) >= 45:
            blocks.append(_section("_… remaining groups not shown — try `/wc group <X>`_"))
            break

    return blocks


def teams_blocks(teams: list[Team]) -> list[dict]:
    """All teams, grouped alphabetically in columns of two."""
    blocks: list[dict] = [_header(f"🏆  WC 2026 — {len(teams)} Teams")]

    sorted_teams = sorted(teams, key=lambda t: t.name)
    # Pair teams into two-column field entries
    fields = []
    for t in sorted_teams:
        fields.append({"type": "mrkdwn", "text": f"*[{t.tla}]* {t.name}"})

    # Slack allows max 10 fields per section block
    for i in range(0, len(fields), 10):
        chunk = fields[i:i + 10]
        blocks.append({"type": "section", "fields": chunk})

    return blocks


def goal_alert_blocks(match: Match, prev: tuple, curr: tuple,
                      goal: Optional[Goal] = None) -> list[dict]:
    """
    Notification block for a goal.
    prev / curr are (home_goals, away_goals) tuples.
    goal: the Goal object if available (paid tier), for scorer/minute info.
    """
    home_prev, _ = prev
    home_curr, away_curr = curr

    if home_curr > home_prev:
        scoring_team = match.home_team.name
        scoring_tla = match.home_team.tla
        winning = home_curr > away_curr
    else:
        scoring_team = match.away_team.name
        scoring_tla = match.away_team.tla
        winning = away_curr > home_curr

    score = match.score.display()
    group = _group_label(match.group) or _stage_label(match.stage)

    if goal:
        goal_type = ""
        if goal.type == "OWN":
            goal_type = "  _(own goal)_"
        elif goal.type == "PENALTY":
            goal_type = "  _(penalty)_"

        detail = f"{goal.scorer_name} {goal.minute_display()}{goal_type}"
        if goal.assist_name:
            detail += f"  ·  assist: {goal.assist_name}"

        blocks = [
            _header(f"⚽  GOAL!  {scoring_team}"),
            _section(f"*{match.home_team.name}*  {score}  *{match.away_team.name}*"),
            _section(detail),
            _context(group),
        ]
    else:
        blocks = [
            _header(f"⚽  GOAL!  {scoring_team}"),
            _section(f"*{match.home_team.name}*  {score}  *{match.away_team.name}*"),
            _context(group),
        ]

    celebration = easter_eggs.goal_celebration(scoring_tla, winning)
    if celebration:
        blocks.append(_section(celebration))

    return blocks


def booking_blocks(match: Match, booking: Booking) -> list[dict]:
    """Yellow or red card notification."""
    if booking.card == "RED":
        emoji, label = "🟥", "Red card"
    elif booking.card == "YELLOW_RED":
        emoji, label = "🟥", "Second yellow / red card"
    else:
        emoji, label = "🟨", "Yellow card"

    team_name = (
        match.home_team.name if booking.team_id == match.home_team.id
        else match.away_team.name
    )
    score = match.score.display()
    group = _group_label(match.group) or _stage_label(match.stage)

    return [
        _header(f"{emoji}  {label}  —  {team_name}"),
        _section(
            f"{booking.player_name}  ({booking.minute}')\n"
            f"*{match.home_team.name}*  {score}  *{match.away_team.name}*"
        ),
        _context(group),
    ]


def lineup_blocks(match: Match) -> list[dict]:
    """Starting XIs and formations for both teams."""
    blocks: list[dict] = [
        _header(f"📋  Line-ups  —  {match.home_team.name} vs {match.away_team.name}"),
    ]
    group = _group_label(match.group) or _stage_label(match.stage)
    blocks.append(_context(group, match.utc_date.strftime("%d %b, %H:%M UTC")))

    for lineup in match.lineups:
        formation = f"  ({lineup.formation})" if lineup.formation else ""
        blocks.append(_divider())
        team_header = f"*{lineup.team.name}*{formation}"
        egg_msg = easter_eggs.lineup_message(lineup.team.tla)
        if egg_msg:
            team_header += f"  ·  {egg_msg}"
        blocks.append(_section(team_header))

        if lineup.starters:
            lines = []
            for p in lineup.starters:
                num = f"{p.shirt_number}." if p.shirt_number else "  "
                lines.append(f"`{num:<3}` {p.name}  _{p.position}_")
            blocks.append(_section("\n".join(lines)))

        if lineup.substitutes:
            subs = ", ".join(p.name for p in lineup.substitutes)
            blocks.append(_section(f"*Subs:* {subs}"))

    if not match.lineups:
        blocks.append(_section("_Line-ups not yet available._"))
        for team in (match.home_team, match.away_team):
            egg_msg = easter_eggs.lineup_message(team.tla)
            if egg_msg:
                blocks.append(_section(egg_msg))

    return blocks


def extra_time_blocks(match: Match) -> list[dict]:
    """Notification that a knockout match is going to extra time."""
    score = match.score.display()
    group = _group_label(match.group) or _stage_label(match.stage)
    return [
        _header(f"⏱️  Extra time!  {match.home_team.name} vs {match.away_team.name}"),
        _section(f"*{match.home_team.name}*  {score}  *{match.away_team.name}*  ·  {group}"),
    ]


def penalty_shootout_blocks(match: Match) -> list[dict]:
    """Notification that a match is going to a penalty shootout."""
    score = match.score.display()
    group = _group_label(match.group) or _stage_label(match.stage)
    return [
        _header(f"🎯  Penalty shootout!  {match.home_team.name} vs {match.away_team.name}"),
        _section(f"*{match.home_team.name}*  {score}  *{match.away_team.name}*  ·  {group}"),
    ]


def match_status_blocks(match: Match, old_status: str) -> list[dict]:
    """Notification block for match starting, half time, full time, etc."""
    new_status = match.status
    duration = match.score.duration
    group = _group_label(match.group) or _stage_label(match.stage)
    score = match.score.display()

    if new_status == "IN_PLAY" and old_status in ("TIMED", "SCHEDULED"):
        headline = f"🟢  Kick off!  {match.home_team.name} vs {match.away_team.name}"
        body = f"*{match.home_team.name}* vs *{match.away_team.name}*  ·  {group}"
    elif new_status == "IN_PLAY" and old_status == "PAUSED":
        if duration == "EXTRA_TIME":
            headline = f"🟢  Extra time second half  {match.home_team.name} vs {match.away_team.name}"
        else:
            headline = f"🟢  Second half underway  {match.home_team.name} vs {match.away_team.name}"
        body = f"*{match.home_team.name}*  {score}  *{match.away_team.name}*  ·  {group}"
    elif new_status == "PAUSED":
        if duration == "EXTRA_TIME":
            headline = f"⏸️  Extra time half time  {match.home_team.name} {score} {match.away_team.name}"
            body = f"*{match.home_team.name}*  {score}  *{match.away_team.name}*  ·  ET HT  ·  {group}"
        else:
            headline = f"⏸️  Half time  {match.home_team.name} {score} {match.away_team.name}"
            body = f"*{match.home_team.name}*  {score}  *{match.away_team.name}*  ·  HT  ·  {group}"
    elif new_status == "FINISHED":
        if duration == "PENALTY_SHOOTOUT":
            suffix = "on penalties"
        elif duration == "EXTRA_TIME":
            suffix = "AET"
        else:
            suffix = "FT"
        headline = f"✅  Full time  {match.home_team.name} {score} {match.away_team.name}"
        body = f"*{match.home_team.name}*  {score}  *{match.away_team.name}*  ·  {suffix}  ·  {group}"
    else:
        headline = f"{_STATUS_EMOJI.get(new_status, '❓')}  {match.home_team.name} vs {match.away_team.name}  —  {new_status}"
        body = f"_{old_status} → {new_status}_"

    return [
        _header(headline),
        _section(body),
    ]


_POSITION_ORDER = ["Goalkeeper", "Defence", "Midfield", "Offence", "Defender",
                   "Midfielder", "Forward", "Attacker"]
_POSITION_GROUP = {
    "Goalkeeper": "Goalkeepers",
    "Defence": "Defenders", "Defender": "Defenders",
    "Midfield": "Midfielders", "Midfielder": "Midfielders",
    "Offence": "Forwards", "Forward": "Forwards", "Attacker": "Forwards",
}
_STAGE_ORDER = [
    "ROUND_OF_32", "ROUND_OF_16", "QUARTER_FINALS",
    "SEMI_FINALS", "THIRD_PLACE", "FINAL",
]
_STAGE_LABEL = {
    "ROUND_OF_32": "Round of 32", "ROUND_OF_16": "Round of 16",
    "QUARTER_FINALS": "Quarter-finals", "SEMI_FINALS": "Semi-finals",
    "THIRD_PLACE": "Third place play-off", "FINAL": "Final",
}


def team_blocks(detail: TeamDetail, standing: Optional[TableRow],
                next_match: Optional[Match], last_match: Optional[Match]) -> list[dict]:
    """Team profile: easter egg, standing, next/last match, squad by position."""
    egg_msg = easter_eggs.lineup_message(detail.tla)
    title = f"🏴  {detail.name}"
    if egg_msg:
        title += f"  ·  {egg_msg}"

    blocks: list[dict] = [_header(title)]

    # Venue + coach
    meta_parts = []
    if detail.venue:
        meta_parts.append(f"🏟️ {detail.venue}")
    if detail.coach_name:
        nat = f" ({detail.coach_nationality})" if detail.coach_nationality else ""
        meta_parts.append(f"👔 {detail.coach_name}{nat}")
    if meta_parts:
        blocks.append(_section("  ·  ".join(meta_parts)))

    # Group standing
    if standing:
        blocks.append(_divider())
        blocks.append(_section(
            f"*Group standing:*  {standing.position}. "
            f"P{standing.played}  W{standing.won}  D{standing.draw}  L{standing.lost}  "
            f"GD{standing.goal_difference:+d}  *{standing.points}pts*"
        ))

    # Next match
    if next_match:
        opp = (next_match.away_team if next_match.home_team.id == detail.id
               else next_match.home_team)
        group = _group_label(next_match.group) or _stage_label(next_match.stage)
        blocks.append(_section(
            f"*Next:* vs *{opp.name}*  ·  "
            f"{next_match.utc_date.strftime('%a %d %b, %H:%M UTC')}  ·  {group}"
        ))

    # Last result
    if last_match and last_match.is_finished:
        opp = (last_match.away_team if last_match.home_team.id == detail.id
               else last_match.home_team)
        blocks.append(_section(
            f"*Last result:* {last_match.home_team.tla} "
            f"{last_match.score.display()} {last_match.away_team.tla}"
            f"  ·  vs *{opp.name}*"
        ))

    # Squad by position
    if detail.squad:
        blocks.append(_divider())
        grouped: dict = {}
        for p in sorted(detail.squad, key=lambda x: x.shirt_number or 99):
            group_name = _POSITION_GROUP.get(p.position, p.position or "Other")
            grouped.setdefault(group_name, []).append(p)

        for group_name in ["Goalkeepers", "Defenders", "Midfielders", "Forwards", "Other"]:
            players = grouped.get(group_name)
            if not players:
                continue
            lines = [f"*{group_name}*"]
            for p in players:
                num = f"{p.shirt_number}." if p.shirt_number else "  "
                lines.append(f"`{num:<3}` {p.name}")
            blocks.append(_section("\n".join(lines)))
            if len(blocks) >= 45:
                break

    return blocks


def scorers_blocks(scorers: list[Scorer]) -> list[dict]:
    """Golden Boot leaderboard."""
    if not scorers:
        return [_header("🥇  WC 2026 — Golden Boot"),
                _section("_No goals scored yet._")]

    header = f"{'#':<3} {'Player':<22} {'Team':<6} {'G':>3} {'A':>3} {'P':>3}"
    sep = "─" * len(header)
    rows = [header, sep]
    for i, s in enumerate(scorers, 1):
        pen = f"({s.penalties})" if s.penalties else "   "
        rows.append(
            f"{i:<3} {s.player_name[:22]:<22} {s.team_tla:<6} "
            f"{s.goals:>3} {s.assists:>3} {pen:>3}"
        )
    return [
        _header("🥇  WC 2026 — Golden Boot"),
        _section("```" + "\n".join(rows) + "```"),
        _context("G = Goals  ·  A = Assists  ·  P = Penalties"),
    ]


def substitution_blocks(match: Match, sub: Substitution) -> list[dict]:
    """Substitution notification."""
    team_name = (match.home_team.name if sub.team_id == match.home_team.id
                 else match.away_team.name)
    score = match.score.display()
    group = _group_label(match.group) or _stage_label(match.stage)
    return [
        _header(f"🔄  {team_name}"),
        _section(
            f"*{sub.player_in}* on for *{sub.player_out}*  ({sub.minute}')\n"
            f"{match.home_team.name}  {score}  {match.away_team.name}"
        ),
        _context(group),
    ]


def h2h_blocks(team1: Team, team2: Team,
               wc_matches: list[Match],
               t1_standing: Optional[TableRow],
               t2_standing: Optional[TableRow]) -> list[dict]:
    """Head-to-head between two teams in WC2026."""
    blocks: list[dict] = [
        _header(f"📊  {team1.name} vs {team2.name}  —  WC 2026"),
    ]

    # WC2026 fixture(s) between them
    meetings = [
        m for m in wc_matches
        if {m.home_team.id, m.away_team.id} == {team1.id, team2.id}
    ]
    if meetings:
        blocks.append(_divider())
        blocks.append(_section("*WC 2026 fixture*"))
        for m in meetings:
            group = _group_label(m.group) or _stage_label(m.stage)
            date_str = m.utc_date.strftime("%a %d %b, %H:%M UTC")
            if m.is_finished:
                blocks.append(_section(
                    f"{m.home_team.tla}  *{m.score.display()}*  {m.away_team.tla}"
                    f"  ·  {group}  ·  {date_str}"
                ))
            else:
                blocks.append(_section(
                    f"{m.home_team.tla} vs {m.away_team.tla}"
                    f"  ·  {group}  ·  {date_str}  ·  [{m.status}]"
                ))
    else:
        blocks.append(_section("_No WC 2026 fixture scheduled between these teams yet._"))

    # Tournament records
    blocks.append(_divider())
    for team, standing in ((team1, t1_standing), (team2, t2_standing)):
        if standing:
            blocks.append(_section(
                f"*{team.name}* — "
                f"P{standing.played}  W{standing.won}  D{standing.draw}  L{standing.lost}  "
                f"GF{standing.goals_for}  GA{standing.goals_against}  "
                f"*{standing.points}pts*"
            ))
        else:
            blocks.append(_section(f"*{team.name}* — no standings data yet"))

    return blocks


def matchday_summary_blocks(matches: list[Match]) -> list[dict]:
    """End-of-day summary of all finished matches."""
    if not matches:
        return [_header("📋  Matchday Summary"),
                _section("_No finished matches today._")]

    date_str = matches[0].utc_date.strftime("%A %d %B")
    blocks: list[dict] = [_header(f"📋  Matchday Summary  —  {date_str}")]

    total_goals = 0
    for m in matches:
        score = m.score.display()
        line = f"*{m.home_team.name}*  {score}  *{m.away_team.name}*"

        # Goal scorers (paid tier)
        scorer_lines = []
        for g in m.goals:
            team_tla = (m.home_team.tla if g.team_id == m.home_team.id
                        else m.away_team.tla)
            label = ""
            if g.type == "OWN":
                label = " (og)"
            elif g.type == "PENALTY":
                label = " (pen)"
            scorer_lines.append(f"  ⚽ {g.scorer_name}{label} {g.minute_display()} [{team_tla}]")
            total_goals += 1

        # Red cards
        for b in m.bookings:
            if b.card in ("RED", "YELLOW_RED"):
                team_tla = (m.home_team.tla if b.team_id == m.home_team.id
                            else m.away_team.tla)
                scorer_lines.append(f"  🟥 {b.player_name} {b.minute}' [{team_tla}]")

        if scorer_lines:
            line += "\n" + "\n".join(scorer_lines)

        blocks.append(_divider())
        blocks.append(_section(line))

        if len(blocks) >= 45:
            break

    blocks.append(_divider())
    blocks.append(_context(f"{len(matches)} matches  ·  {total_goals} goals"))
    return blocks


def bracket_blocks(matches: list[Match]) -> list[dict]:
    """Knockout stage bracket grouped by round."""
    knockout = [m for m in matches if not m.group]

    if not knockout:
        return [
            _header("🏆  WC 2026 — Knockout Bracket"),
            _section("_Bracket available after the group stage._"),
        ]

    by_stage: dict = {}
    for m in knockout:
        by_stage.setdefault(m.stage, []).append(m)

    blocks: list[dict] = [_header("🏆  WC 2026 — Knockout Bracket")]

    for stage_key in _STAGE_ORDER:
        stage_matches = by_stage.get(stage_key)
        if not stage_matches:
            continue
        label = _STAGE_LABEL.get(stage_key, stage_key.replace("_", " ").title())
        blocks.append(_divider())
        blocks.append(_section(f"*{label}*"))

        lines = []
        for m in sorted(stage_matches, key=lambda x: x.utc_date):
            home = m.home_team.name if m.home_team.id else "TBD"
            away = m.away_team.name if m.away_team.id else "TBD"
            date_str = m.utc_date.strftime("%d %b")
            if m.is_finished:
                lines.append(f"{home}  *{m.score.display()}*  {away}  ·  {date_str}")
            elif m.is_live:
                lines.append(f"🟢 {home}  {m.score.display()}  {away}  ·  LIVE")
            else:
                lines.append(f"{home} vs {away}  ·  {date_str}")
        blocks.append(_section("\n".join(lines)))

        if len(blocks) >= 45:
            blocks.append(_section("_… more rounds not shown_"))
            break

    return blocks


def help_blocks() -> list[dict]:
    return [
        _header("🏆  WC 2026 Footbot"),
        _section(
            "*Available commands:*\n"
            "`/wc fixtures`            — all fixtures grouped by date\n"
            "`/wc today`               — today's matches\n"
            "`/wc next`                — next 3 upcoming matches\n"
            "`/wc live`                — matches currently in progress\n"
            "`/wc table`               — all group standings\n"
            "`/wc group <X>`           — fixtures + table for one group  _(e.g. `/wc group A`)_\n"
            "`/wc team <name>`         — squad, coach & stats  _(e.g. `/wc team scotland`)_\n"
            "`/wc lineup <team>`       — starting XI for a team  _(e.g. `/wc lineup scotland`)_\n"
            "`/wc top`                 — Golden Boot leaderboard\n"
            "`/wc h2h <team> <team>`   — head to head  _(e.g. `/wc h2h scotland england`)_\n"
            "`/wc bracket`             — knockout stage bracket\n"
            "`/wc teams`               — all 48 teams\n"
            "`/wc help`                — show this message"
        ),
    ]
