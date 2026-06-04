"""
Quick smoke test for the football-data.org client.
Run from the footbot/ directory after adding your token to .env:
    python test_client.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from football_data import client


def print_separator(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def test_matches():
    print_separator("All WC2026 Matches (first 5)")
    matches = client.get_matches()
    for m in matches[:5]:
        print(f"  [{m.status:10}] {m.utc_date.strftime('%d %b %H:%M UTC')}  "
              f"{m.home_team.tla} {m.score.display()} {m.away_team.tla}"
              f"  ({m.stage} / {m.group or 'knockout'})")
    print(f"  ... {len(matches)} total matches")


def test_today():
    print_separator("Today's Matches")
    matches = client.get_today_matches()
    if not matches:
        print("  No matches today.")
    for m in matches:
        print(f"  {m.utc_date.strftime('%H:%M UTC')}  "
              f"{m.home_team.name} vs {m.away_team.name}  [{m.status}]")


def test_standings():
    print_separator("Group Standings (Group A)")
    groups = client.get_standings()
    group_a = next((g for g in groups if g.group == "GROUP_A"), None)
    if not group_a:
        print("  No GROUP_A standings yet (tournament may not have started).")
        if groups:
            group_a = groups[0]
            print(f"  Showing {group_a.group} instead.")
        else:
            return
    for row in group_a.table:
        print(f"  {row.position}. {row.team.name:25} P{row.played} W{row.won} D{row.draw} L{row.lost}  "
              f"GD{row.goal_difference:+d}  {row.points}pts")


def test_teams():
    print_separator("Teams (first 8)")
    teams = client.get_teams()
    for t in teams[:8]:
        print(f"  [{t.tla}] {t.name}")
    print(f"  ... {len(teams)} total teams")


if __name__ == "__main__":
    try:
        test_matches()
        test_today()
        test_standings()
        test_teams()
        print("\nAll checks passed!")
    except Exception as e:
        print(f"\nERROR: {e}")
        raise
