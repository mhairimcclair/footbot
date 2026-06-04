"""
Team-specific easter eggs for Slack messages.

To add eggs for a new team, add an entry to TEAM_EGGS keyed by the
three-letter TLA (e.g. "ENG", "BRA"). All fields are optional.

  goal_flags      — shown on every goal by this team
  winning_message — appended (below the flags) when the team is winning
  lineup_messages — one is picked at random when the team's lineup is posted
"""
import random
from typing import Optional

TEAM_EGGS: dict = {
    # Totally unbiased messages
    "SCO": {
        "flag": ":flag-scotland:",
        "goal_flags": ":flag-scotland: :flag-scotland: :flag-scotland: :flag-scotland: flag-scotland: :flag-scotland:",
        "winning_message": "YASSSSSS! SCOTLAND'S ON FIRE :fire:!!!! ",
        "lineup_messages": [
            "WE'RE GONNA DEEP FRY YOUR HOTDOGS",
            "NO SCOTLAND NO PARTY",
            "We'll Be Coming Down the Road",
        ],
    },
    # Add more teams here, e.g.:
    #"BRA": {
    #    "flag": ":flag-br:",
    #    "goal_flags": ":flag-br: :flag-br: :flag-br: :flag-br:",
    #    "winning_message": "Samba time! 🕺",
    #    "lineup_messages": [
    #        "Five-time world champions",
    #    ],
    #},
}


def goal_celebration(tla: str, winning: bool) -> Optional[str]:
    """
    Returns a celebration string if the team has easter eggs, else None.
    Includes a winning message if the team is currently ahead.
    """
    egg = TEAM_EGGS.get(tla.upper())
    if not egg:
        return None
    flags = egg.get("goal_flags", "")
    if winning and egg.get("winning_message"):
        return f"{flags}\n{egg['winning_message']}"
    return flags or None


def lineup_message(tla: str) -> Optional[str]:
    """Returns 'flag message' for the team's lineup, or None."""
    egg = TEAM_EGGS.get(tla.upper())
    if not egg:
        return None
    messages = egg.get("lineup_messages", [])
    if not messages:
        return None
    flag = egg.get("flag", "")
    msg = random.choice(messages)
    return f"{flag} {msg}".strip()
