"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=20, pattern=r'^[^<>&"\x00-\x1f]+$'),
]


class CreateRoomRequest(BaseModel):
    display_name: DisplayName
    total_rounds: int | None = Field(default=None, ge=1, le=10, description="Number of rounds (default from server config)")


class JoinRoomRequest(BaseModel):
    display_name: DisplayName


class RoomPlayer(BaseModel):
    display_name: str
    score: int = 0


class RoomInfo(BaseModel):
    room_code: str
    status: str = Field(description="waiting | in_progress | finished | abandoned")
    joinable: bool
    player_count: int
    min_players: int | None = None
    max_players: int | None = None
    total_rounds: int
    current_round: int
    players: list[RoomPlayer]


class JoinResponse(BaseModel):
    room_code: str
    player_id: int
    display_name: str
    token: str = Field(description="Session token: pass as ?token= when opening the WebSocket")
    room: RoomInfo


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    total_score: int
    games_played: int
    wins: int
    best_score: int


class PlayerStats(BaseModel):
    display_name: str
    games_played: int
    wins: int
    win_rate: float
    total_score: int
    average_score: float
    best_score: int
    correct_guesses: int
    rounds_drawn: int


class GamePlayer(BaseModel):
    display_name: str
    score: int
    is_winner: bool


class GameSummary(BaseModel):
    room_code: str
    status: str
    total_rounds: int
    started_at: datetime | None
    ended_at: datetime | None
    players: list[GamePlayer]


class RoundDetail(BaseModel):
    round_number: int
    drawer: str | None
    word: str
    started_at: datetime | None
    ended_at: datetime | None
    correct_guesses: int
    total_guesses: int


class GameDetail(BaseModel):
    room_code: str
    status: str
    current_round: int
    total_rounds: int
    created_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    players: list[GamePlayer]
    rounds: list[RoundDetail]
