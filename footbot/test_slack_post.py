"""
Posts test messages to your Slack channel to verify the bot token,
channel ID, and message formatting are all working correctly.

Covers: goals, full time, extra time, penalties, red card, lineups,
        and paid-tier scorer info.

Run from footbot/:
    python test_slack_post.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import SLACK_BOT_TOKEN, SLACK_CHANNEL
from slack.formatter import (
    goal_alert_blocks, match_status_blocks,
    extra_time_blocks, penalty_shootout_blocks,
    booking_blocks, lineup_blocks,
)
from football_data.models import (
    Match, Score, Team, Goal, Booking, Lineup, LineupPlayer,
)
from datetime import datetime, timezone

client = WebClient(token=SLACK_BOT_TOKEN)

SCO = Team(id=1178, name="Scotland", short_name="Scotland", tla="SCO", crest="")
ENG = Team(id=66,   name="England",  short_name="England",  tla="ENG", crest="")
FRA = Team(id=773,  name="France",   short_name="France",   tla="FRA", crest="")
BRA = Team(id=759,  name="Brazil",   short_name="Brazil",   tla="BRA", crest="")


def post(blocks: list[dict], label: str):
    print(f"Posting: {label}...")
    try:
        result = client.chat_postMessage(channel=SLACK_CHANNEL, blocks=blocks)
        print(f"  OK  ts={result['ts']}")
    except SlackApiError as e:
        print(f"  ERROR: {e.response['error']}")
        raise


def make_match(home: Team, away: Team, status: str, home_score: int, away_score: int,
               duration="REGULAR", stage="GROUP_STAGE", group="GROUP_A",
               winner=None) -> Match:
    return Match(
        id=9999,
        utc_date=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        status=status,
        stage=stage,
        group=group,
        home_team=home,
        away_team=away,
        score=Score(
            home=home_score, away=away_score,
            home_half=0, away_half=0,
            home_extra=None, away_extra=None,
            home_penalties=None, away_penalties=None,
            winner=winner, duration=duration,
        ),
    )


# ── Group stage goals ─────────────────────────────────────────
print("\n--- Group stage goals ---")
post(goal_alert_blocks(make_match(SCO, ENG, "IN_PLAY", 1, 0), prev=(0, 0), curr=(1, 0)),
     "Goal — Scotland 1-0")

post(goal_alert_blocks(make_match(SCO, ENG, "IN_PLAY", 2, 0), prev=(1, 0), curr=(2, 0)),
     "Goal — Scotland 2-0")

post(goal_alert_blocks(make_match(SCO, ENG, "IN_PLAY", 2, 1), prev=(2, 0), curr=(2, 1)),
     "Goal — England consolation 2-1")

post(match_status_blocks(make_match(SCO, ENG, "FINISHED", 2, 1, winner="HOME_TEAM"),
                         old_status="IN_PLAY"),
     "Full time — Scotland 2-1 England")

# ── Extra time ────────────────────────────────────────────────
print("\n--- Extra time ---")
et_match = make_match(SCO, FRA, "IN_PLAY", 1, 1,
                      duration="EXTRA_TIME", stage="QUARTER_FINALS", group=None)
post(extra_time_blocks(et_match), "Extra time alert")

post(match_status_blocks(
        make_match(SCO, FRA, "PAUSED", 1, 1, duration="EXTRA_TIME",
                   stage="QUARTER_FINALS", group=None),
        old_status="IN_PLAY"),
     "Extra time half time")

post(goal_alert_blocks(
        make_match(SCO, FRA, "IN_PLAY", 2, 1, duration="EXTRA_TIME",
                   stage="QUARTER_FINALS", group=None),
        prev=(1, 1), curr=(2, 1)),
     "Goal in extra time — Scotland 2-1")

post(match_status_blocks(
        make_match(SCO, FRA, "FINISHED", 2, 1, duration="EXTRA_TIME",
                   stage="QUARTER_FINALS", group=None, winner="HOME_TEAM"),
        old_status="IN_PLAY"),
     "Full time AET — Scotland 2-1 France")

# ── Penalty shootout ──────────────────────────────────────────
print("\n--- Penalty shootout ---")
pen_match = make_match(SCO, BRA, "IN_PLAY", 1, 1,
                       duration="PENALTY_SHOOTOUT", stage="SEMI_FINALS", group=None)
post(penalty_shootout_blocks(pen_match), "Penalty shootout alert")

post(match_status_blocks(
        make_match(SCO, BRA, "FINISHED", 1, 1, duration="PENALTY_SHOOTOUT",
                   stage="SEMI_FINALS", group=None, winner="HOME_TEAM"),
        old_status="IN_PLAY"),
     "Full time on penalties — Scotland beat Brazil")

# ── Red card ──────────────────────────────────────────────────
print("\n--- Red card ---")
red_match = make_match(SCO, ENG, "IN_PLAY", 1, 0)
post(booking_blocks(red_match,
                    Booking(minute=67, team_id=ENG.id,
                            player_name="Declan Rice", card="YELLOW_RED")),
     "Red card — Declan Rice 67'")

post(booking_blocks(red_match,
                    Booking(minute=82, team_id=ENG.id,
                            player_name="Harry Maguire", card="RED")),
     "Straight red — Harry Maguire 82'")

# ── Lineups ───────────────────────────────────────────────────
print("\n--- Lineups ---")
lineup_match = make_match(SCO, ENG, "TIMED", 0, 0)
lineup_match.lineups = [
    Lineup(
        team=SCO, formation="4-3-3",
        starters=[
            LineupPlayer("Angus Gunn",       "Goalkeeper",  1),
            LineupPlayer("Anthony Ralston",  "Right Back",  2),
            LineupPlayer("Grant Hanley",     "Centre-Back", 5),
            LineupPlayer("Scott McKenna",    "Centre-Back", 6),
            LineupPlayer("Andrew Robertson","Left Back",    3),
            LineupPlayer("Billy Gilmour",    "Midfielder",  8),
            LineupPlayer("Callum McGregor",  "Midfielder",  14),
            LineupPlayer("John McGinn",      "Midfielder",  7),
            LineupPlayer("Scott McTominay",  "Midfielder",  4),
            LineupPlayer("Che Adams",        "Forward",     9),
            LineupPlayer("Lyndon Dykes",     "Forward",     10),
        ],
        substitutes=[
            LineupPlayer("Craig Gordon",     "Goalkeeper",  13),
            LineupPlayer("Ryan Christie",    "Midfielder",  11),
            LineupPlayer("Kevin Nisbet",     "Forward",     20),
        ],
    ),
    Lineup(
        team=ENG, formation="4-3-3",
        starters=[
            LineupPlayer("Jordan Pickford", "Goalkeeper",  1),
            LineupPlayer("Kyle Walker",     "Right Back",  2),
            LineupPlayer("John Stones",     "Centre-Back", 5),
            LineupPlayer("Harry Maguire",   "Centre-Back", 6),
            LineupPlayer("Luke Shaw",       "Left Back",   3),
            LineupPlayer("Declan Rice",     "Midfielder",  4),
            LineupPlayer("Jude Bellingham", "Midfielder",  22),
            LineupPlayer("Phil Foden",      "Midfielder",  11),
            LineupPlayer("Bukayo Saka",     "Forward",     7),
            LineupPlayer("Harry Kane",      "Forward",     9),
            LineupPlayer("Marcus Rashford", "Forward",     10),
        ],
        substitutes=[
            LineupPlayer("Nick Pope",       "Goalkeeper",  13),
            LineupPlayer("Trent Alexander-Arnold", "Midfielder", 12),
            LineupPlayer("Ollie Watkins",   "Forward",     15),
        ],
    ),
]
post(lineup_blocks(lineup_match), "Lineups — Scotland vs England")

# ── Paid tier: goal with scorer info ──────────────────────────
print("\n--- Paid tier scorer info ---")
scorer_match = make_match(SCO, ENG, "IN_PLAY", 1, 0)
post(goal_alert_blocks(scorer_match, prev=(0, 0), curr=(1, 0),
                       goal=Goal(minute=23, injury_time=None, type="REGULAR",
                                 team_id=SCO.id, scorer_name="Scott McTominay",
                                 assist_name="John McGinn")),
     "Goal with scorer — McTominay 23'")

pen_scorer_match = make_match(SCO, ENG, "IN_PLAY", 2, 0)
post(goal_alert_blocks(pen_scorer_match, prev=(1, 0), curr=(2, 0),
                       goal=Goal(minute=55, injury_time=None, type="PENALTY",
                                 team_id=SCO.id, scorer_name="Lyndon Dykes",
                                 assist_name=None)),
     "Penalty goal — Dykes 55'")

og_match = make_match(SCO, ENG, "IN_PLAY", 3, 0)
post(goal_alert_blocks(og_match, prev=(2, 0), curr=(3, 0),
                       goal=Goal(minute=78, injury_time=2, type="OWN",
                                 team_id=ENG.id, scorer_name="Harry Maguire",
                                 assist_name=None)),
     "Own goal — Maguire 78+2'")

print("\nDone!")
