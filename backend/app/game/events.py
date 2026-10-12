"""WebSocket message structure.

Every message, in both directions, is a JSON envelope:

    {"type": "<event_name>", "payload": {...}}

Client -> server payloads are validated by the models below; unknown or
malformed messages are answered with an `error` event.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def msg(type_: str, **payload: Any) -> dict[str, Any]:
    return {"type": type_, "payload": payload}


class ReadyPayload(BaseModel):
    ready: bool


class StrokePayload(BaseModel):
    """A chunk of a stroke. Points are normalised to 0..1 so every client
    can reconstruct the drawing at any resolution."""

    stroke_id: str = Field(min_length=1, max_length=48, pattern=r"^[A-Za-z0-9_-]+$")
    tool: Literal["brush", "eraser"] = "brush"
    color: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    size: int = Field(default=6, ge=1, le=64)
    points: list[tuple[float, float]] = Field(min_length=1, max_length=200)
    end: bool = False

    @field_validator("points")
    @classmethod
    def _in_range(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for x, y in v:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError("stroke points must be within 0..1")
        return v


class GuessPayload(BaseModel):
    text: str = Field(min_length=1, max_length=64)

    @field_validator("text", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> Any:
        if isinstance(v, str):
            return " ".join(v.split())
        return v


CLIENT_EVENTS = {
    "ping": "Heartbeat. Server answers with `pong`.",
    "ready": "{ready: bool} Toggle readiness in the lobby.",
    "start_game": "Host only. Requires min players connected and everyone ready.",
    "stroke": "Drawer only. {stroke_id, tool, color, size, points:[[x,y]...], end}",
    "clear_canvas": "Drawer only. Clears the shared canvas.",
    "guess": "{text} Guessers only, while the round is active.",
    "leave": "Leave the room permanently.",
}

SERVER_EVENTS = {
    "state_sync": "Full snapshot sent on (re)connect. The secret word is included only for the drawer.",
    "player_joined": "A new player joined the lobby.",
    "player_left": "A player left (reason: left | timeout).",
    "player_connected": "A player's socket connected / reconnected.",
    "player_disconnected": "A player's socket dropped (grace period starts).",
    "player_ready": "{player_id, ready}",
    "host_changed": "{host_id}",
    "game_started": "{total_rounds, players}",
    "round_started": "{round_number, drawer_id, hint, remaining, round_seconds, word?} word only for the drawer.",
    "stroke": "A drawing chunk (sent to everyone except the drawer).",
    "canvas_cleared": "Canvas cleared by the drawer.",
    "chat": "A wrong guess shown to the room: {player_id, name, text}.",
    "correct_guess": "{player_id, name, points, order} - never includes the guess text.",
    "scores_updated": "{scores: [{player_id, score}]}",
    "timer": "{round_number, remaining} - once per second.",
    "round_ended": "{reason, word, results, scores, next_in, is_last}",
    "waiting_for_players": "Paused between rounds until enough players are connected.",
    "game_ended": "{reason, leaderboard}",
    "error": "{code, message} - only sent to the offending client.",
    "pong": "Heartbeat reply.",
}
