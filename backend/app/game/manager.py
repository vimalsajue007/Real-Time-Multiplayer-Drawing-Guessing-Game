"""GameManager: registry of live rooms and room creation / joining rules."""
from __future__ import annotations

import secrets

from .. import persistence
from ..config import Settings
from ..database import DbRunner
from .errors import GameError
from .room import GameRoom, PlayerState

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class GameManager:
    def __init__(self, settings: Settings, db: DbRunner) -> None:
        self.settings = settings
        self.db = db
        self.rooms: dict[str, GameRoom] = {}

    def get(self, code: str) -> GameRoom | None:
        return self.rooms.get(code.upper())

    async def _unique_code(self) -> str:
        for _ in range(25):
            code = "".join(secrets.choice(ALPHABET) for _ in range(5))
            if code in self.rooms:
                continue
            if await self.db.run(persistence.code_exists, code):
                continue
            return code
        raise GameError("code_generation_failed", "Could not allocate a room code.", 503)

    async def create_room(self, display_name: str, total_rounds: int | None) -> tuple[GameRoom, PlayerState]:
        total = total_rounds or self.settings.default_rounds
        if not 1 <= total <= self.settings.max_rounds:
            raise GameError("invalid_rounds", f"Rounds must be between 1 and {self.settings.max_rounds}.", 422)
        code = await self._unique_code()
        room_id = await self.db.run(persistence.create_room, code, total)
        room = GameRoom(self, code, room_id, total)
        self.rooms[code] = room
        player = await room.join(display_name)
        return room, player

    async def join_room(self, code: str, display_name: str) -> tuple[GameRoom, PlayerState]:
        code = code.strip().upper()
        room = self.rooms.get(code)
        if room is None:
            if await self.db.run(persistence.room_status, code) is None:
                raise GameError("room_not_found", "Room not found.", 404)
            raise GameError("room_inactive", "This room is no longer active.", 403)
        return room, await room.join(display_name)

    async def room_known(self, code: str) -> bool:
        return await self.db.run(persistence.room_status, code) is not None

    def room_info(self, room: GameRoom) -> dict:
        s = self.settings
        return {
            "room_code": room.code,
            "status": room.public_status,
            "joinable": room.public_status == "waiting" and len(room.active_players()) < s.max_players,
            "player_count": len(room.active_players()),
            "min_players": s.min_players,
            "max_players": s.max_players,
            "total_rounds": room.total_rounds,
            "current_round": room.round_number,
            "players": [{"display_name": p.name, "score": p.score} for p in room.active_players()],
        }

    async def shutdown(self) -> None:
        for room in list(self.rooms.values()):
            room.shutdown()
        self.rooms.clear()
