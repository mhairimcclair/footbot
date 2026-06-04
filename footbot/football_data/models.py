from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Team:
    id: int
    name: str
    short_name: str
    tla: str  # three-letter abbreviation, e.g. "ENG"
    crest: str

    @classmethod
    def from_dict(cls, d: dict) -> "Team":
        return cls(
            id=d["id"],
            name=d["name"],
            short_name=d.get("shortName", d["name"]),
            tla=d.get("tla", ""),
            crest=d.get("crest", ""),
        )


@dataclass
class Score:
    home: Optional[int]
    away: Optional[int]
    home_half: Optional[int]
    away_half: Optional[int]
    home_extra: Optional[int]
    away_extra: Optional[int]
    home_penalties: Optional[int]
    away_penalties: Optional[int]
    winner: Optional[str]   # "HOME_TEAM", "AWAY_TEAM", "DRAW"
    duration: str           # "REGULAR", "EXTRA_TIME", "PENALTY_SHOOTOUT"

    @classmethod
    def from_dict(cls, d: dict) -> "Score":
        ft = d.get("fullTime", {})
        ht = d.get("halfTime", {})
        et = d.get("extraTime", {})
        pen = d.get("penalties", {})
        return cls(
            home=ft.get("home"),
            away=ft.get("away"),
            home_half=ht.get("home"),
            away_half=ht.get("away"),
            home_extra=et.get("home"),
            away_extra=et.get("away"),
            home_penalties=pen.get("home"),
            away_penalties=pen.get("away"),
            winner=d.get("winner"),
            duration=d.get("duration", "REGULAR"),
        )

    def display(self) -> str:
        if self.home is None or self.away is None:
            return "- v -"
        s = f"{self.home} - {self.away}"
        if self.duration == "PENALTY_SHOOTOUT" and self.home_penalties is not None:
            s += f"  (pens {self.home_penalties}-{self.away_penalties})"
        elif self.duration == "EXTRA_TIME" and self.home_extra is not None:
            s += "  (aet)"
        return s


@dataclass
class Goal:
    minute: int
    injury_time: Optional[int]
    type: str           # "REGULAR", "OWN", "PENALTY"
    team_id: int
    scorer_name: str
    assist_name: Optional[str]

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        return cls(
            minute=d.get("minute") or 0,
            injury_time=d.get("injuryTime"),
            type=d.get("type", "REGULAR"),
            team_id=(d.get("team") or {}).get("id", 0),
            scorer_name=(d.get("scorer") or {}).get("name", "Unknown"),
            assist_name=(d.get("assist") or {}).get("name") if d.get("assist") else None,
        )

    def minute_display(self) -> str:
        if self.injury_time:
            return f"{self.minute}+{self.injury_time}'"
        return f"{self.minute}'"


@dataclass
class Booking:
    minute: int
    team_id: int
    player_name: str
    card: str   # "YELLOW", "RED", "YELLOW_RED" (second yellow → red)

    @classmethod
    def from_dict(cls, d: dict) -> "Booking":
        return cls(
            minute=d.get("minute") or 0,
            team_id=(d.get("team") or {}).get("id", 0),
            player_name=(d.get("player") or {}).get("name", "Unknown"),
            card=d.get("card", "YELLOW"),
        )


@dataclass
class Substitution:
    minute: int
    team_id: int
    player_out: str
    player_in: str

    @classmethod
    def from_dict(cls, d: dict) -> "Substitution":
        return cls(
            minute=d.get("minute") or 0,
            team_id=(d.get("team") or {}).get("id", 0),
            player_out=(d.get("playerOut") or {}).get("name", "Unknown"),
            player_in=(d.get("playerIn") or {}).get("name", "Unknown"),
        )


@dataclass
class SquadPlayer:
    id: int
    name: str
    position: str
    nationality: str
    shirt_number: Optional[int]

    @classmethod
    def from_dict(cls, d: dict) -> "SquadPlayer":
        return cls(
            id=d.get("id", 0),
            name=d.get("name", "Unknown"),
            position=d.get("position", ""),
            nationality=d.get("nationality", ""),
            shirt_number=d.get("shirtNumber"),
        )


@dataclass
class TeamDetail:
    id: int
    name: str
    short_name: str
    tla: str
    crest: str
    venue: Optional[str]
    coach_name: Optional[str]
    coach_nationality: Optional[str]
    squad: list[SquadPlayer] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "TeamDetail":
        coach = d.get("coach") or {}
        return cls(
            id=d["id"],
            name=d["name"],
            short_name=d.get("shortName", d["name"]),
            tla=d.get("tla", ""),
            crest=d.get("crest", ""),
            venue=d.get("venue"),
            coach_name=coach.get("name"),
            coach_nationality=coach.get("nationality"),
            squad=[SquadPlayer.from_dict(p) for p in d.get("squad", [])],
        )


@dataclass
class Scorer:
    player_name: str
    team_name: str
    team_tla: str
    goals: int
    assists: int
    penalties: int

    @classmethod
    def from_dict(cls, d: dict) -> "Scorer":
        player = d.get("player") or {}
        team = d.get("team") or {}
        return cls(
            player_name=player.get("name", "Unknown"),
            team_name=team.get("name", ""),
            team_tla=team.get("tla", ""),
            goals=d.get("goals") or 0,
            assists=d.get("assists") or 0,
            penalties=d.get("penalties") or 0,
        )


@dataclass
class LineupPlayer:
    name: str
    position: str
    shirt_number: Optional[int]

    @classmethod
    def from_dict(cls, d: dict) -> "LineupPlayer":
        p = d.get("player", d)  # some endpoints nest under "player", some don't
        return cls(
            name=p.get("name", "Unknown"),
            position=p.get("position", ""),
            shirt_number=p.get("shirtNumber"),
        )


@dataclass
class Lineup:
    team: Team
    formation: Optional[str]
    starters: list[LineupPlayer] = field(default_factory=list)
    substitutes: list[LineupPlayer] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Lineup":
        return cls(
            team=Team.from_dict(d["team"]),
            formation=d.get("formation"),
            starters=[LineupPlayer.from_dict(p) for p in d.get("startXI", [])],
            substitutes=[LineupPlayer.from_dict(p) for p in d.get("substitutes", [])],
        )

    @property
    def is_available(self) -> bool:
        return len(self.starters) > 0


@dataclass
class Match:
    id: int
    utc_date: datetime
    status: str
    stage: str
    group: Optional[str]
    home_team: Team
    away_team: Team
    score: Score
    goals: list[Goal] = field(default_factory=list)
    bookings: list[Booking] = field(default_factory=list)
    lineups: list[Lineup] = field(default_factory=list)
    substitutions: list[Substitution] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Match":
        return cls(
            id=d["id"],
            utc_date=datetime.fromisoformat(d["utcDate"].replace("Z", "+00:00")),
            status=d["status"],
            stage=d["stage"],
            group=d.get("group"),
            home_team=Team.from_dict(d["homeTeam"]),
            away_team=Team.from_dict(d["awayTeam"]),
            score=Score.from_dict(d["score"]),
            goals=[Goal.from_dict(g) for g in d.get("goals", [])],
            bookings=[Booking.from_dict(b) for b in d.get("bookings", [])],
            lineups=[Lineup.from_dict(l) for l in d.get("lineups", [])],
            substitutions=[Substitution.from_dict(s) for s in d.get("substitutions", [])],
        )

    @property
    def is_live(self) -> bool:
        return self.status in ("IN_PLAY", "PAUSED")

    @property
    def is_finished(self) -> bool:
        return self.status == "FINISHED"

    @property
    def is_upcoming(self) -> bool:
        return self.status in ("SCHEDULED", "TIMED")

    def lineup_for(self, team_id: int) -> Optional[Lineup]:
        return next((l for l in self.lineups if l.team.id == team_id), None)


@dataclass
class TableRow:
    position: int
    team: Team
    played: int
    won: int
    draw: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int

    @classmethod
    def from_dict(cls, d: dict) -> "TableRow":
        return cls(
            position=d["position"],
            team=Team.from_dict(d["team"]),
            played=d["playedGames"],
            won=d["won"],
            draw=d["draw"],
            lost=d["lost"],
            goals_for=d["goalsFor"],
            goals_against=d["goalsAgainst"],
            goal_difference=d["goalDifference"],
            points=d["points"],
        )


@dataclass
class StandingGroup:
    group: str
    table: list[TableRow] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "StandingGroup":
        return cls(
            group=d.get("group", ""),
            table=[TableRow.from_dict(row) for row in d.get("table", [])],
        )
