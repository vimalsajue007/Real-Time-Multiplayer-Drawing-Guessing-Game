from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response

from ..game.errors import GameError
from ..schemas import CreateRoomRequest, JoinResponse, JoinRoomRequest, RoomInfo
from ..security import make_token, verify_token

router = APIRouter(prefix="/api", tags=["rooms"])


def _join_response(request: Request, room, player) -> dict:
    mgr = request.app.state.manager
    return {
        "room_code": room.code,
        "player_id": player.id,
        "display_name": player.name,
        "token": make_token(request.app.state.settings.secret_key, room.code, player.id),
        "room": mgr.room_info(room),
    }


@router.post("/rooms", response_model=JoinResponse, status_code=201, summary="Create a room (you become the host)")
async def create_room(body: CreateRoomRequest, request: Request):
    room, player = await request.app.state.manager.create_room(body.display_name, body.total_rounds)
    return _join_response(request, room, player)


@router.post("/rooms/{room_code}/join", response_model=JoinResponse, summary="Join a room that is waiting in its lobby")
async def join_room(room_code: str, body: JoinRoomRequest, request: Request):
    room, player = await request.app.state.manager.join_room(room_code, body.display_name)
    return _join_response(request, room, player)


@router.get("/rooms/{room_code}", response_model=RoomInfo, summary="Get public room information (never the secret word)")
async def get_room(room_code: str, request: Request):
    mgr = request.app.state.manager
    code = room_code.strip().upper()
    room = mgr.get(code)
    if room is not None:
        return mgr.room_info(room)
    from .. import persistence, queries

    info = await mgr.db.run(queries.room_summary_from_db, code)
    if info is None:
        raise HTTPException(404, "Room not found.")
    return info


@router.post("/rooms/{room_code}/leave", status_code=204, summary="Leave a room (Bearer session token)")
async def leave_room(room_code: str, request: Request, authorization: str = Header(default="")):
    code = room_code.strip().upper()
    token = authorization.removeprefix("Bearer ").strip()
    pid = verify_token(request.app.state.settings.secret_key, code, token)
    if pid is None:
        raise GameError("unauthorized", "Invalid session token.", 401)
    room = request.app.state.manager.get(code)
    if room is not None:
        await room.remove_player(pid, "left")
    return Response(status_code=204)
