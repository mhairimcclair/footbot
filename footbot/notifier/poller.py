"""
Polls football-data.org for today's matches.
Detects goals, bookings, lineup availability, and status transitions.

Goal detection strategy:
  - Paid tier: compare goals array by (minute, scorer) — accurate, gives scorer info.
  - Free tier (goals array empty): fall back to comparing score tuples.

State is held in memory — if the bot restarts mid-match it re-learns
current state on the next poll and won't re-fire old alerts.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from football_data import client
from football_data.models import Match, Goal, Booking, Substitution
from slack import formatter

logger = logging.getLogger(__name__)

# match_id → last known Match snapshot
_state: dict[int, Match] = {}

_NOTIFY_TRANSITIONS = {"IN_PLAY", "PAUSED", "FINISHED"}


def _goal_key(g: Goal) -> tuple:
    """Unique identifier for a goal — minute + scorer + type."""
    return (g.minute, g.injury_time, g.scorer_name, g.type)


def _booking_key(b: Booking) -> tuple:
    return (b.minute, b.player_name, b.card)


def _sub_key(s: Substitution) -> tuple:
    return (s.minute, s.team_id, s.player_out, s.player_in)


def _handle_match(match: Match, post_fn: Callable[[list], None]) -> None:
    prev = _state.get(match.id)

    if prev is None:
        _state[match.id] = match
        return

    # ── Goal detection ──────────────────────────────────────────────────────
    if match.goals:
        # Paid tier: use goals array — accurate scorer info
        prev_keys = {_goal_key(g) for g in prev.goals}
        for goal in match.goals:
            if _goal_key(goal) not in prev_keys:
                home_score = sum(1 for g in match.goals if g.team_id == match.home_team.id)
                away_score = sum(1 for g in match.goals if g.team_id == match.away_team.id)
                prev_h = sum(1 for g in prev.goals if g.team_id == match.home_team.id)
                prev_a = sum(1 for g in prev.goals if g.team_id == match.away_team.id)
                blocks = formatter.goal_alert_blocks(
                    match,
                    prev=(prev_h, prev_a),
                    curr=(home_score, away_score),
                    goal=goal,
                )
                post_fn(blocks)
    else:
        # Free tier fallback: compare score tuples
        prev_score = (prev.score.home, prev.score.away)
        curr_score = (match.score.home, match.score.away)
        if None not in (curr_score[0], curr_score[1]) and prev_score != curr_score:
            prev_h, prev_a = prev_score[0] or 0, prev_score[1] or 0
            curr_h, curr_a = curr_score
            for i in range(max(curr_h - prev_h, 0)):
                post_fn(formatter.goal_alert_blocks(
                    match, prev=(prev_h + i, prev_a), curr=(prev_h + i + 1, prev_a)
                ))
            for i in range(max(curr_a - prev_a, 0)):
                post_fn(formatter.goal_alert_blocks(
                    match, prev=(curr_h, prev_a + i), curr=(curr_h, prev_a + i + 1)
                ))

    # ── Booking detection ───────────────────────────────────────────────────
    prev_booking_keys = {_booking_key(b) for b in prev.bookings}
    for booking in match.bookings:
        if _booking_key(booking) not in prev_booking_keys:
            # Only alert for red cards by default — yellow spam gets annoying fast
            if booking.card in ("RED", "YELLOW_RED"):
                post_fn(formatter.booking_blocks(match, booking))
            else:
                logger.debug("Yellow card: %s %s'", booking.player_name, booking.minute)

    # ── Substitution detection ──────────────────────────────────────────────
    prev_sub_keys = {_sub_key(s) for s in prev.substitutions}
    for sub in match.substitutions:
        if _sub_key(sub) not in prev_sub_keys:
            post_fn(formatter.substitution_blocks(match, sub))

    # ── Lineup detection ────────────────────────────────────────────────────
    # Fire once when lineups first become available (typically ~60 min pre-KO)
    prev_had_lineups = any(l.is_available for l in prev.lineups)
    curr_has_lineups = any(l.is_available for l in match.lineups)
    if not prev_had_lineups and curr_has_lineups:
        post_fn(formatter.lineup_blocks(match))

    # ── Duration transition (extra time / penalties) ────────────────────────
    if match.score.duration != prev.score.duration:
        if match.score.duration == "EXTRA_TIME":
            post_fn(formatter.extra_time_blocks(match))
        elif match.score.duration == "PENALTY_SHOOTOUT":
            post_fn(formatter.penalty_shootout_blocks(match))

    # ── Status transition ───────────────────────────────────────────────────
    if match.status != prev.status and match.status in _NOTIFY_TRANSITIONS:
        blocks = formatter.match_status_blocks(match, old_status=prev.status)
        post_fn(blocks)

    _state[match.id] = match


def _has_active_or_imminent(matches: list[Match]) -> bool:
    now = datetime.now(tz=timezone.utc)
    soon = now + timedelta(hours=2)
    for m in matches:
        if m.is_live or m.status == "PAUSED":
            return True
        if m.is_upcoming and m.utc_date <= soon:
            return True
    return False


def _poll(post_fn: Callable[[list], None]) -> None:
    try:
        matches = client.get_today_matches()
        if not _has_active_or_imminent(matches):
            logger.debug("Poll: no active or imminent matches — skipping")
            return
        logger.debug("Poll: %d matches today, checking for updates", len(matches))
        for match in matches:
            _handle_match(match, post_fn)
    except Exception:
        logger.exception("Polling error — will retry next cycle")


def start(post_fn: Callable[[list], None], interval_seconds: int = 60) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _poll,
        trigger="interval",
        seconds=interval_seconds,
        kwargs={"post_fn": post_fn},
        id="match_poller",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Match poller started — checking every %ds", interval_seconds)
    return scheduler
