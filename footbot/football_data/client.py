import time
import threading
import logging
from typing import Optional
import requests
from datetime import date

from config import FOOTBALL_DATA_TOKEN, FOOTBALL_DATA_BASE_URL, WC_COMPETITION, FOOTBALL_DATA_MIN_INTERVAL
from football_data.models import Match, StandingGroup, Team, TeamDetail, Scorer
from football_data import cache

logger = logging.getLogger(__name__)

_HEADERS = {"X-Auth-Token": FOOTBALL_DATA_TOKEN}
_MIN_INTERVAL = FOOTBALL_DATA_MIN_INTERVAL
_last_request_at: float = 0.0
_rate_lock = threading.Lock()
_MAX_RETRIES = 3


def _get(path: str, params: Optional[dict] = None) -> dict:
    global _last_request_at
    url = f"{FOOTBALL_DATA_BASE_URL}{path}"

    for attempt in range(1, _MAX_RETRIES + 1):
        with _rate_lock:
            elapsed = time.monotonic() - _last_request_at
            if elapsed < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - elapsed)
            logger.debug("GET %s %s", url, params or "")
            response = requests.get(url, headers=_HEADERS, params=params, timeout=10)
            _last_request_at = time.monotonic()

        if response.status_code == 429:
            retry_after = int(response.headers.get("X-RequestCounter-Reset", 60))
            logger.warning("Rate limited (attempt %d/%d) — waiting %ds",
                           attempt, _MAX_RETRIES, retry_after)
            if attempt < _MAX_RETRIES:
                time.sleep(retry_after)
                continue
            response.raise_for_status()

        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"Failed to GET {url} after {_MAX_RETRIES} attempts")  # unreachable


def get_matches(status: Optional[str] = None, match_day: Optional[int] = None) -> list[Match]:
    """All WC2026 matches, optionally filtered by status or matchday. Cached 5 min."""
    params: dict = {}
    if status:
        params["status"] = status
    if match_day:
        params["matchday"] = match_day
    key = f"matches:{status}:{match_day}"
    return cache.get(key, ttl=300, fn=lambda: [
        Match.from_dict(m)
        for m in _get(f"/competitions/{WC_COMPETITION}/matches", params or None).get("matches", [])
    ])


def get_today_matches() -> list[Match]:
    """Today's matches. Cached 90s — used by both the poller and slash commands."""
    today = date.today().isoformat()
    return cache.get("today", ttl=90, fn=lambda: [
        Match.from_dict(m)
        for m in _get(f"/competitions/{WC_COMPETITION}/matches",
                      {"dateFrom": today, "dateTo": today}).get("matches", [])
    ])


def get_live_matches() -> list[Match]:
    """Live matches. Cached 30s — short enough to catch goals promptly."""
    return cache.get("live", ttl=30, fn=lambda: [
        Match.from_dict(m)
        for m in _get(f"/competitions/{WC_COMPETITION}/matches",
                      {"status": "LIVE"}).get("matches", [])
    ])


def get_match(match_id: int) -> Match:
    data = _get(f"/matches/{match_id}")
    return Match.from_dict(data)


def get_standings() -> list[StandingGroup]:
    """Group standings. Cached 5 min."""
    return cache.get("standings", ttl=300, fn=lambda: [
        StandingGroup.from_dict(s)
        for s in _get(f"/competitions/{WC_COMPETITION}/standings").get("standings", [])
    ])


def get_teams() -> list[Team]:
    """All teams. Cached 1 hour — changes only at tournament start."""
    return cache.get("teams", ttl=3600, fn=lambda: [
        Team.from_dict(t)
        for t in _get(f"/competitions/{WC_COMPETITION}/teams").get("teams", [])
    ])


def get_team_detail(team_id: int) -> TeamDetail:
    """Full squad + coach for one team. Cached 1 hour."""
    return cache.get(f"team:{team_id}", ttl=3600,
                     fn=lambda: TeamDetail.from_dict(_get(f"/teams/{team_id}")))


def get_scorers(limit: int = 10) -> list[Scorer]:
    """Golden Boot leaderboard. Cached 5 min."""
    return cache.get(f"scorers:{limit}", ttl=300, fn=lambda: [
        Scorer.from_dict(s)
        for s in _get(f"/competitions/{WC_COMPETITION}/scorers",
                      {"limit": limit}).get("scorers", [])
    ])
