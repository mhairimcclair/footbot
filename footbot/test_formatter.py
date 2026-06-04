"""
Prints Block Kit JSON for each formatter function using live data.
Paste any output block into https://app.slack.com/block-kit-builder to preview.

Run from footbot/:
    python test_formatter.py
"""
import sys, os, json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))

from football_data import client
from football_data.models import (
    Team, TeamDetail, SquadPlayer, Scorer, Substitution,
    Match, Score, TableRow,
)
from slack import formatter


def show(label: str, blocks: list[dict]):
    print(f"\n{'='*60}")
    print(f"  {label}  ({len(blocks)} blocks)")
    print('='*60)
    print(json.dumps({"blocks": blocks}, indent=2))


SCO = Team(id=1178, name="Scotland", short_name="Scotland", tla="SCO", crest="")
ENG = Team(id=66,   name="England",  short_name="England",  tla="ENG", crest="")


def fake_match(home, away, status="FINISHED", h=2, a=1, stage="GROUP_STAGE", group="GROUP_A"):
    return Match(
        id=9999,
        utc_date=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        status=status, stage=stage, group=group,
        home_team=home, away_team=away,
        score=Score(home=h, away=a, home_half=1, away_half=0,
                    home_extra=None, away_extra=None,
                    home_penalties=None, away_penalties=None,
                    winner=None, duration="REGULAR"),
    )


# ── Fetch live data ───────────────────────────────────────────
print("Fetching data from football-data.org...")
matches   = client.get_matches()
today     = client.get_today_matches()
live      = client.get_live_matches()
standings = client.get_standings()
teams     = client.get_teams()
scorers   = client.get_scorers()
print(f"  {len(matches)} matches | {len(today)} today | {len(live)} live | "
      f"{len(standings)} groups | {len(teams)} teams | {len(scorers)} scorers\n")

# ── Existing formatters ───────────────────────────────────────
show("FIXTURES (first 10)",          formatter.fixtures_blocks(matches[:10]))
show("TODAY",                        formatter.today_blocks(today))
show("NEXT 3",                       formatter.next_blocks(matches))
show("LIVE",                         formatter.live_blocks(live))
show("STANDINGS — Group A",          formatter.standings_blocks(standings, filter_group="A"))
show("TEAMS",                        formatter.teams_blocks(teams))
show("HELP",                         formatter.help_blocks())
show("BRACKET",                      formatter.bracket_blocks(matches))

finished = [m for m in matches if m.is_finished and m.score.home is not None]
if finished:
    m = finished[0]
    show("GOAL ALERT (live data)",   formatter.goal_alert_blocks(
        m, (max(0, m.score.home - 1), m.score.away), (m.score.home, m.score.away)))

# ── Golden Boot ───────────────────────────────────────────────
show("GOLDEN BOOT (live)",           formatter.scorers_blocks(scorers))

# ── Team profile ──────────────────────────────────────────────
sco_team = next((t for t in teams if t.tla == "SCO"), None)
if sco_team:
    detail = client.get_team_detail(sco_team.id)
    sco_standing = next(
        (r for g in standings for r in g.table if r.team.id == sco_team.id), None
    )
    sco_matches = [m for m in matches
                   if m.home_team.id == sco_team.id or m.away_team.id == sco_team.id]
    now = datetime.now(tz=timezone.utc)
    next_m = next((m for m in sorted(sco_matches, key=lambda x: x.utc_date)
                   if m.is_upcoming and m.utc_date > now), None)
    last_m = next((m for m in sorted(sco_matches, key=lambda x: x.utc_date, reverse=True)
                   if m.is_finished), None)
    show("TEAM — Scotland",          formatter.team_blocks(detail, sco_standing, next_m, last_m))
else:
    # Fake team detail for preview
    fake_detail = TeamDetail(
        id=1178, name="Scotland", short_name="Scotland", tla="SCO", crest="",
        venue="Hampden Park", coach_name="Steve Clarke", coach_nationality="Scottish",
        squad=[
            SquadPlayer(1, "Angus Gunn",       "Goalkeeper", "Scottish", 1),
            SquadPlayer(2, "Grant Hanley",      "Defence",    "Scottish", 5),
            SquadPlayer(3, "Scott McTominay",   "Midfield",   "Scottish", 4),
            SquadPlayer(4, "Lyndon Dykes",      "Offence",    "Scottish", 9),
        ],
    )
    fake_row = TableRow(position=1, team=SCO, played=2, won=2, draw=0,
                        lost=0, goals_for=4, goals_against=1,
                        goal_difference=3, points=6)
    show("TEAM — Scotland (fake)",   formatter.team_blocks(fake_detail, fake_row, None, None))

# ── Substitution ──────────────────────────────────────────────
sub = Substitution(minute=72, team_id=SCO.id,
                   player_out="Che Adams", player_in="Lyndon Dykes")
show("SUBSTITUTION",                 formatter.substitution_blocks(fake_match(SCO, ENG, "IN_PLAY", 1, 0), sub))

# ── Head to head ─────────────────────────────────────────────
sco_t = next((t for t in teams if t.tla == "SCO"), SCO)
eng_t = next((t for t in teams if t.tla == "ENG"), ENG)
sco_row = next((r for g in standings for r in g.table if r.team.id == sco_t.id), None)
eng_row = next((r for g in standings for r in g.table if r.team.id == eng_t.id), None)
show("H2H — Scotland vs England",   formatter.h2h_blocks(sco_t, eng_t, matches, sco_row, eng_row))

# ── Matchday summary ──────────────────────────────────────────
if finished:
    show("MATCHDAY SUMMARY (live)",  formatter.matchday_summary_blocks(finished[:5]))
else:
    show("MATCHDAY SUMMARY (fake)",  formatter.matchday_summary_blocks([
        fake_match(SCO, ENG, "FINISHED", 2, 1),
        fake_match(ENG, SCO, "FINISHED", 0, 3),
    ]))

print("\nDone. Paste any block above into https://app.slack.com/block-kit-builder to preview.")
