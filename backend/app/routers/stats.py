from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from .. import queries
from ..game.events import CLIENT_EVENTS, SERVER_EVENTS
from ..schemas import GameDetail, GameSummary, LeaderboardEntry, PlayerStats

router = APIRouter(prefix="/api", tags=["history & stats"])


@router.get("/health", tags=["meta"], summary="Liveness probe")
async def health():
    return {"status": "ok"}


@router.get("/protocol", tags=["meta"], summary="WebSocket protocol reference (envelope + events)")
async def protocol():
    return {
        "endpoint": "/ws/{room_code}?token=<session token from create/join>",
        "envelope": {"type": "string", "payload": "object"},
        "close_codes": {
            "4401": "invalid token / not a member",
            "4403": "room inactive",
            "4404": "room not found",
            "4409": "replaced by a newer connection",
        },
        "client_events": CLIENT_EVENTS,
        "server_events": SERVER_EVENTS,
    }


@router.get("/games/history", response_model=list[GameSummary], summary="Recently completed games")
async def history(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return await request.app.state.db.run(queries.game_history, limit, offset)


@router.get("/games/{room_code}", response_model=GameDetail, summary="Details of a completed game")
async def game_detail(room_code: str, request: Request):
    detail = await request.app.state.db.run(queries.game_detail, room_code.strip().upper())
    if detail is None:
        raise HTTPException(404, "Game not found.")
    if detail["status"] not in ("finished", "abandoned"):
        # Words of a running game must never be exposed.
        raise HTTPException(403, "Details are available once the game has ended.")
    return detail


@router.get("/leaderboard", response_model=list[LeaderboardEntry], summary="All-time leaderboard")
async def leaderboard(request: Request, limit: int = Query(10, ge=1, le=100)):
    return await request.app.state.db.run(queries.leaderboard, limit)


@router.get("/players/{display_name}/stats", response_model=PlayerStats, summary="Player statistics by display name")
async def player_stats(display_name: str, request: Request):
    stats = await request.app.state.db.run(queries.player_stats, display_name)
    if stats is None:
        raise HTTPException(404, "No completed games for this player.")
    return stats
