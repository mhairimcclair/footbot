"""
Simulates match lifecycles through the poller to verify all notification
types fire correctly.

Simulations:
  1. Group stage — Scotland 4-1 England  (basic flow)
  2. Knockout — Scotland 2-1 France AET  (extra time goal)
  3. Knockout — Scotland beat Brazil on pens  (penalty shootout)
  4. Cards — yellow (silent) + red card alert
  5. Lineups — auto-posted when lineups first appear
  6. Paid tier — goal alert with scorer name + minute

Run from footbot/:
    python test_poller.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone
from football_data.models import Match, Score, Team, Goal, Booking, Lineup, LineupPlayer, Substitution
from notifier import poller


# ── helpers ───────────────────────────────────────────────────────────────────

posted_messages: list[list[dict]] = []

def fake_post(blocks: list[dict]) -> None:
    posted_messages.append(blocks)


def show_posted(label: str) -> None:
    if not posted_messages:
        print(f"  [{label}]  — no messages posted")
        return
    for i, blocks in enumerate(posted_messages):
        tag = f"[{label}]" if len(posted_messages) == 1 else f"[{label} #{i+1}]"
        print(f"\n{'─'*60}")
        print(f"  {tag}")
        print('─'*60)
        print(json.dumps({"blocks": blocks}, indent=2))
    posted_messages.clear()


def reset():
    """Clear poller state between simulations."""
    poller._state.clear()


SCO = Team(id=1178, name="Scotland", short_name="Scotland", tla="SCO", crest="")
ENG = Team(id=66,   name="England",  short_name="England",  tla="ENG", crest="")
FRA = Team(id=773,  name="France",   short_name="France",   tla="FRA", crest="")
BRA = Team(id=759,  name="Brazil",   short_name="Brazil",   tla="BRA", crest="")


def make_match(home: Team, away: Team, status: str,
               home_goals, away_goals,
               ht_home=None, ht_away=None,
               duration="REGULAR",
               stage="GROUP_STAGE", group="GROUP_A",
               match_id=9999,
               goals=None, bookings=None, lineups=None,
               substitutions=None) -> Match:
    return Match(
        id=match_id,
        utc_date=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
        status=status,
        stage=stage,
        group=group,
        home_team=home,
        away_team=away,
        score=Score(
            home=home_goals, away=away_goals,
            home_half=ht_home, away_half=ht_away,
            home_extra=None, away_extra=None,
            home_penalties=None, away_penalties=None,
            winner=None, duration=duration,
        ),
        goals=goals or [],
        bookings=bookings or [],
        lineups=lineups or [],
        substitutions=substitutions or [],
    )


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ══════════════════════════════════════════════════════════════
# Simulation 1: Group stage — Scotland 4-1 England
# ══════════════════════════════════════════════════════════════
section("Simulation 1: Group stage — Scotland vs England")
reset()

poller._handle_match(make_match(SCO, ENG, "TIMED", None, None), fake_post)
print("\nStep 1: TIMED (first seen)")
show_posted("TIMED")                            # expect: nothing

poller._handle_match(make_match(SCO, ENG, "IN_PLAY", 0, 0), fake_post)
print("\nStep 2: Kick off")
show_posted("Kick off")                         # expect: kick-off alert

poller._handle_match(make_match(SCO, ENG, "IN_PLAY", 1, 0), fake_post)
print("\nStep 3: Scotland score — 1-0")
show_posted("Goal SCO 1-0")

poller._handle_match(make_match(SCO, ENG, "PAUSED", 1, 0, ht_home=1, ht_away=0), fake_post)
print("\nStep 4: Half time")
show_posted("HT")

poller._handle_match(make_match(SCO, ENG, "IN_PLAY", 2, 0, ht_home=1, ht_away=0), fake_post)
print("\nStep 5: Scotland score — 2-0")
show_posted("Goal SCO 2-0")                     # expect: goal + second half underway

poller._handle_match(make_match(SCO, ENG, "IN_PLAY", 2, 1, ht_home=1, ht_away=0), fake_post)
print("\nStep 6: England consolation — 2-1")
show_posted("Goal ENG 2-1")

poller._handle_match(make_match(SCO, ENG, "IN_PLAY", 4, 1, ht_home=1, ht_away=0), fake_post)
print("\nStep 7: Two Scotland goals in one poll — 4-1")
show_posted("Two goals")                        # expect: 2 × goal alerts

poller._handle_match(make_match(SCO, ENG, "FINISHED", 4, 1, ht_home=1, ht_away=0), fake_post)
print("\nStep 8: Full time — Scotland win!")
show_posted("FT")


# ══════════════════════════════════════════════════════════════
# Simulation 2: Knockout — Scotland 2-1 France AET
# ══════════════════════════════════════════════════════════════
section("Simulation 2: Knockout — Scotland vs France (extra time)")
reset()

kw = dict(stage="QUARTER_FINALS", group=None, match_id=8888)

poller._handle_match(make_match(SCO, FRA, "TIMED", None, None, **kw), fake_post)
poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 0, 0, **kw), fake_post)
print("\nStep 1: Kick off")
show_posted("Kick off")

poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 1, 0, **kw), fake_post)
print("\nStep 2: Scotland score — 1-0")
show_posted("Goal SCO 1-0")

poller._handle_match(make_match(SCO, FRA, "PAUSED", 1, 0, ht_home=1, ht_away=0, **kw), fake_post)
print("\nStep 3: Half time")
show_posted("HT")

poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 1, 0, ht_home=1, ht_away=0, **kw), fake_post)
print("\nStep 4: Second half underway")
show_posted("2nd half")

# France equalise in 90+3
poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 1, 1, ht_home=1, ht_away=0, **kw), fake_post)
print("\nStep 5: France equalise — 1-1")
show_posted("Goal FRA 1-1")

# Duration flips to EXTRA_TIME
poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 1, 1, ht_home=1, ht_away=0,
                                duration="EXTRA_TIME", **kw), fake_post)
print("\nStep 6: Extra time begins")
show_posted("Extra time")                       # expect: extra time alert

poller._handle_match(make_match(SCO, FRA, "PAUSED", 1, 1, ht_home=1, ht_away=0,
                                duration="EXTRA_TIME", **kw), fake_post)
print("\nStep 7: Extra time half time")
show_posted("ET HT")

poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 1, 1, ht_home=1, ht_away=0,
                                duration="EXTRA_TIME", **kw), fake_post)
print("\nStep 8: Extra time second half")
show_posted("ET 2nd half")

# Scotland score the winner in ET
poller._handle_match(make_match(SCO, FRA, "IN_PLAY", 2, 1, ht_home=1, ht_away=0,
                                duration="EXTRA_TIME", **kw), fake_post)
print("\nStep 9: Scotland score in extra time — 2-1")
show_posted("Goal SCO AET 2-1")

poller._handle_match(make_match(SCO, FRA, "FINISHED", 2, 1, ht_home=1, ht_away=0,
                                duration="EXTRA_TIME", **kw), fake_post)
print("\nStep 10: Full time AET — Scotland win!")
show_posted("FT AET")                           # expect: "Full time … AET"


# ══════════════════════════════════════════════════════════════
# Simulation 3: Knockout — Scotland beat Brazil on penalties
# ══════════════════════════════════════════════════════════════
section("Simulation 3: Knockout — Scotland vs Brazil (penalties)")
reset()

kw = dict(stage="SEMI_FINALS", group=None, match_id=7777)

poller._handle_match(make_match(SCO, BRA, "TIMED", None, None, **kw), fake_post)
poller._handle_match(make_match(SCO, BRA, "IN_PLAY", 0, 0, **kw), fake_post)
poller._handle_match(make_match(SCO, BRA, "PAUSED", 0, 0, ht_home=0, ht_away=0, **kw), fake_post)
poller._handle_match(make_match(SCO, BRA, "IN_PLAY", 0, 0, ht_home=0, ht_away=0, **kw), fake_post)
poller._handle_match(make_match(SCO, BRA, "IN_PLAY", 1, 0, ht_home=0, ht_away=0, **kw), fake_post)
print("\nStep 1–5: Normal time (Scotland score 1-0, Brazil equalise 1-1)")
poller._handle_match(make_match(SCO, BRA, "IN_PLAY", 1, 1, ht_home=0, ht_away=0, **kw), fake_post)
show_posted("Goals + KO + HT")

# Goes to ET — still 1-1 after 120'
poller._handle_match(make_match(SCO, BRA, "IN_PLAY", 1, 1, ht_home=0, ht_away=0,
                                duration="EXTRA_TIME", **kw), fake_post)
print("\nStep 6: Extra time — still level")
show_posted("Extra time")                       # expect: extra time alert

# Duration flips to PENALTY_SHOOTOUT
poller._handle_match(make_match(SCO, BRA, "IN_PLAY", 1, 1, ht_home=0, ht_away=0,
                                duration="PENALTY_SHOOTOUT", **kw), fake_post)
print("\nStep 7: Penalty shootout!")
show_posted("Penalty shootout")                 # expect: penalty shootout alert

poller._handle_match(make_match(SCO, BRA, "FINISHED", 1, 1, ht_home=0, ht_away=0,
                                duration="PENALTY_SHOOTOUT", **kw), fake_post)
print("\nStep 8: Full time — Scotland win on penalties!")
show_posted("FT on pens")                       # expect: "Full time … on penalties"


# ══════════════════════════════════════════════════════════════
# Simulation 4: Cards
# ══════════════════════════════════════════════════════════════
section("Simulation 4: Cards — yellow (silent) + red card")
reset()

base = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=6666)
poller._handle_match(base, fake_post)
show_posted("First seen")

# Yellow card — should be silent (just logged)
yellow = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=6666,
                    bookings=[Booking(minute=34, team_id=ENG.id,
                                      player_name="Declan Rice", card="YELLOW")])
poller._handle_match(yellow, fake_post)
print("\nStep 1: Yellow card — Declan Rice 34'")
show_posted("Yellow card")                      # expect: nothing (silent)

# Red card — should alert
red = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=6666,
                 bookings=[
                     Booking(minute=34, team_id=ENG.id, player_name="Declan Rice", card="YELLOW"),
                     Booking(minute=67, team_id=ENG.id, player_name="Declan Rice", card="YELLOW_RED"),
                 ])
poller._handle_match(red, fake_post)
print("\nStep 2: Second yellow / red — Declan Rice 67'")
show_posted("Red card")                         # expect: 🟥 red card alert


# ══════════════════════════════════════════════════════════════
# Simulation 5: Lineup detection
# ══════════════════════════════════════════════════════════════
section("Simulation 5: Lineup auto-post")
reset()

no_lineup = make_match(SCO, ENG, "TIMED", None, None, match_id=5555)
poller._handle_match(no_lineup, fake_post)
show_posted("TIMED no lineup")                  # expect: nothing

sco_starters = [
    LineupPlayer("Angus Gunn",      "Goalkeeper", 1),
    LineupPlayer("Anthony Ralston", "Right Back", 2),
    LineupPlayer("Grant Hanley",    "Centre-Back", 5),
    LineupPlayer("Scott McKenna",   "Centre-Back", 6),
    LineupPlayer("Andrew Robertson","Left Back",   3),
    LineupPlayer("Billy Gilmour",   "Midfielder",  8),
    LineupPlayer("Callum McGregor", "Midfielder",  14),
    LineupPlayer("John McGinn",     "Midfielder",  7),
    LineupPlayer("Scott McTominay", "Midfielder",  4),
    LineupPlayer("Che Adams",       "Forward",     9),
    LineupPlayer("Lyndon Dykes",    "Forward",     10),
]
eng_starters = [
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
]

with_lineup = make_match(SCO, ENG, "TIMED", None, None, match_id=5555, lineups=[
    Lineup(team=SCO, formation="4-3-3", starters=sco_starters,
           substitutes=[LineupPlayer("Craig Gordon", "Goalkeeper", 13)]),
    Lineup(team=ENG, formation="4-3-3", starters=eng_starters,
           substitutes=[LineupPlayer("Nick Pope", "Goalkeeper", 13)]),
])
poller._handle_match(with_lineup, fake_post)
print("\nStep 1: Lineups appear (~60 min before KO)")
show_posted("Lineup alert")                     # expect: 📋 lineup message


# ══════════════════════════════════════════════════════════════
# Simulation 6: Paid tier — goal with scorer info
# ══════════════════════════════════════════════════════════════
section("Simulation 6: Paid tier — goal with scorer name + minute")
reset()

base = make_match(SCO, ENG, "IN_PLAY", 0, 0, match_id=4444)
poller._handle_match(base, fake_post)
show_posted("Kick off etc")

# Scotland score — goals array populated (paid tier)
sco_goal = Goal(minute=23, injury_time=None, type="REGULAR",
                team_id=SCO.id, scorer_name="Scott McTominay",
                assist_name="John McGinn")
with_goal = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=4444,
                       goals=[sco_goal])
poller._handle_match(with_goal, fake_post)
print("\nStep 1: Scotland score — McTominay 23' (paid tier, scorer info)")
show_posted("Goal with scorer")                 # expect: scorer name + assist

# Penalty — different goal type
pen_goal = Goal(minute=55, injury_time=None, type="PENALTY",
                team_id=SCO.id, scorer_name="Lyndon Dykes",
                assist_name=None)
with_pen = make_match(SCO, ENG, "IN_PLAY", 2, 0, match_id=4444,
                      goals=[sco_goal, pen_goal])
poller._handle_match(with_pen, fake_post)
print("\nStep 2: Scotland penalty — Dykes 55'")
show_posted("Penalty goal")                     # expect: scorer + "(penalty)"

# Own goal (England own goal)
og = Goal(minute=78, injury_time=2, type="OWN",
          team_id=ENG.id, scorer_name="Harry Maguire",
          assist_name=None)
with_og = make_match(SCO, ENG, "IN_PLAY", 3, 0, match_id=4444,
                     goals=[sco_goal, pen_goal, og])
poller._handle_match(with_og, fake_post)
print("\nStep 3: Maguire own goal 78+2'")
show_posted("Own goal")                         # expect: scorer + "(own goal)"


# ══════════════════════════════════════════════════════════════
# Simulation 7: Substitutions
# ══════════════════════════════════════════════════════════════
section("Simulation 7: Substitutions")
reset()

base = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=3333)
poller._handle_match(base, fake_post)
show_posted("First seen")                           # expect: nothing

# One Scotland sub (Dykes on for Adams, 62')
sub1 = Substitution(minute=62, team_id=SCO.id,
                    player_out="Che Adams", player_in="Lyndon Dykes")
with_sub1 = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=3333,
                       substitutions=[sub1])
poller._handle_match(with_sub1, fake_post)
print("\nStep 1: Scotland sub — Dykes on for Adams (62')")
show_posted("Sub SCO")                              # expect: 🔄 alert

# Same sub again (should NOT re-fire — dedup check)
poller._handle_match(with_sub1, fake_post)
print("\nStep 2: Same sub again — dedup check")
show_posted("Sub dedup")                            # expect: nothing

# England double sub (two new subs in one poll)
sub2 = Substitution(minute=71, team_id=ENG.id,
                    player_out="Harry Kane", player_in="Ollie Watkins")
sub3 = Substitution(minute=71, team_id=ENG.id,
                    player_out="Phil Foden", player_in="Jack Grealish")
with_subs23 = make_match(SCO, ENG, "IN_PLAY", 1, 0, match_id=3333,
                         substitutions=[sub1, sub2, sub3])
poller._handle_match(with_subs23, fake_post)
print("\nStep 3: England double sub (Kane off, Foden off)")
show_posted("Double sub ENG")                       # expect: 2 × 🔄 alerts


print("\n" + "=" * 60)
print("  All simulations complete.")
print("=" * 60)
