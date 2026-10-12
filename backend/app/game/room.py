"""GameRoom: authoritative, in-memory state machine for one room.

All state mutations happen while holding `self.lock`, so concurrent WebSocket
messages and timer callbacks can never interleave. The server is the single
source of truth: clients only send *intents* (ready, stroke, guess, ...) which
are validated here. Scores are computed exclusively on the server.
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .. import persistence
from . import rules
from .errors import GameError
from .events import GuessPayload, ReadyPayload, StrokePayload, msg
from .words import pick_word

if TYPE_CHECKING:  # pragma: no cover
    from .manager import GameManager

log = logging.getLogger(__name__)


class Phase(str, Enum):
    LOBBY = "lobby"
    DRAWING = "drawing"
    ROUND_END = "round_end"
    FINISHED = "finished"


@dataclass
class PlayerState:
    id: int
    name: str
    seq: int
    ready: bool = False
    score: int = 0
    connected: bool = False
    left: bool = False
    ws: Any = None


@dataclass
class RoundState:
    number: int
    drawer_id: int
    word: str
    duration: float
    started: float
    db_id: int | None = None
    guessed: dict[int, int] = field(default_factory=dict)   # player_id -> points
    gained: dict[int, int] = field(default_factory=dict)    # player_id -> points this round
    strokes: list[dict] = field(default_factory=list)
    stroke_index: dict[str, dict] = field(default_factory=dict)
    point_count: int = 0

    def remaining(self, now: float) -> float:
        return max(0.0, self.duration - (now - self.started))


class GameRoom:
    def __init__(self, manager: "GameManager", code: str, db_id: int, total_rounds: int) -> None:
        self.manager = manager
        self.settings = manager.settings
        self.code = code
        self.db_id = db_id
        self.total_rounds = total_rounds
        self.lock = asyncio.Lock()
        self.players: dict[int, PlayerState] = {}
        self.host_id: int | None = None
        self.phase = Phase.LOBBY
        self.round: RoundState | None = None
        self.round_number = 0
        self.rounds_completed = 0
        self.last_drawer_id: int | None = None
        self.used_words: set[str] = set()
        self.last_result: dict | None = None
        self.leaderboard: list[dict] | None = None
        self.closed = False
        self._seq = 0
        self._timers: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ helpers
    def _now(self) -> float:
        return asyncio.get_running_loop().time()

    def active_players(self) -> list[PlayerState]:
        return [p for p in self.players.values() if not p.left]

    def connected_players(self) -> list[PlayerState]:
        return [p for p in self.players.values() if p.connected and not p.left]

    @property
    def public_status(self) -> str:
        if self.closed and self.phase != Phase.FINISHED:
            return "abandoned"
        return {
            Phase.LOBBY: "waiting",
            Phase.DRAWING: "in_progress",
            Phase.ROUND_END: "in_progress",
            Phase.FINISHED: "finished",
        }[self.phase]

    async def _db(self, fn, *args, **kwargs):
        """Persistence must never stall or crash the live game."""
        try:
            return await self.manager.db.run(fn, *args, **kwargs)
        except Exception:
            log.exception("database error in %s", getattr(fn, "__name__", fn))
            return None

    async def _send(self, p: PlayerState, message: dict) -> None:
        if p.ws is None:
            return
        try:
            await p.ws.send_json(message)
        except Exception:
            log.debug("send to player %s failed", p.id)

    async def _broadcast(self, message: dict, exclude: int | None = None) -> None:
        targets = [p for p in self.players.values() if p.ws is not None and p.id != exclude]
        if targets:
            await asyncio.gather(*(self._send(p, message) for p in targets))

    async def _send_error(self, pid: int, code: str, message: str) -> None:
        p = self.players.get(pid)
        if p:
            await self._send(p, msg("error", code=code, message=message))

    @staticmethod
    async def _close_ws(ws: Any, code: int = 1000) -> None:
        try:
            await ws.close(code=code)
        except Exception:
            pass

    def _public(self, p: PlayerState) -> dict:
        r = self.round
        in_round = r is not None and self.phase in (Phase.DRAWING, Phase.ROUND_END)
        return {
            "id": p.id,
            "name": p.name,
            "score": p.score,
            "ready": p.ready or p.id == self.host_id,
            "connected": p.connected,
            "left": p.left,
            "is_host": p.id == self.host_id,
            "is_drawer": bool(in_round and r.drawer_id == p.id),
            "has_guessed": bool(in_round and p.id in r.guessed),
        }

    def _scores_payload(self) -> list[dict]:
        return [{"player_id": p.id, "score": p.score} for p in self.players.values()]

    def snapshot(self, pid: int) -> dict:
        r = self.round
        snap: dict[str, Any] = {
            "room_code": self.code,
            "phase": self.phase.value,
            "you": pid,
            "host_id": self.host_id,
            "players": [self._public(p) for p in self.players.values()],
            "total_rounds": self.total_rounds,
            "round_number": self.round_number,
            "min_players": self.settings.min_players,
            "max_players": self.settings.max_players,
            "round_seconds": self.settings.round_seconds,
            "drawer_id": None,
            "hint": None,
            "remaining": 0,
            "strokes": [],
            "word": None,
            "result": None,
            "leaderboard": None,
        }
        if r is not None and self.phase == Phase.DRAWING:
            snap.update(
                drawer_id=r.drawer_id,
                hint=rules.mask_word(r.word),
                remaining=math.ceil(r.remaining(self._now())),
                strokes=[dict(s, points=list(s["points"])) for s in r.strokes],
            )
            if pid == r.drawer_id:
                snap["word"] = r.word  # only the drawer ever sees it
        elif self.phase == Phase.ROUND_END and r is not None:
            snap["drawer_id"] = r.drawer_id
            snap["result"] = self.last_result
        elif self.phase == Phase.FINISHED:
            snap["leaderboard"] = self.leaderboard
        return snap

    # ------------------------------------------------------------------- timers
    def _cancel(self, key: str) -> None:
        t = self._timers.pop(key, None)
        if t is not None and t is not asyncio.current_task():
            t.cancel()

    def _cancel_prefix(self, prefix: str) -> None:
        for key in [k for k in self._timers if k.startswith(prefix)]:
            self._cancel(key)

    def _cancel_all(self, keep: tuple[str, ...] = ()) -> None:
        for key in [k for k in self._timers if k not in keep]:
            self._cancel(key)

    def _schedule(self, key: str, delay: float, fn, *args) -> None:
        self._cancel(key)

        async def runner() -> None:
            me = asyncio.current_task()
            try:
                await asyncio.sleep(delay)
                async with self.lock:
                    if self.closed:
                        return
                    await fn(*args)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("timer %s failed", key)
            finally:
                if self._timers.get(key) is me:
                    self._timers.pop(key, None)

        self._timers[key] = asyncio.get_running_loop().create_task(runner())

    def shutdown(self) -> None:
        self.closed = True
        for key in list(self._timers):
            t = self._timers.pop(key)
            t.cancel()

    # --------------------------------------------------------------- membership
    async def join(self, name: str) -> PlayerState:
        async with self.lock:
            if self.closed or self.phase == Phase.FINISHED:
                raise GameError("room_inactive", "This room is no longer active.", 403)
            if self.phase != Phase.LOBBY:
                raise GameError("game_in_progress", "This game has already started.", 409)
            if len(self.active_players()) >= self.settings.max_players:
                raise GameError("room_full", "This room is full.", 409)
            if any(p.name.casefold() == name.casefold() for p in self.active_players()):
                raise GameError("name_taken", "That display name is already used in this room.", 409)
            pid = await self.manager.db.run(persistence.add_player, self.db_id, name)
            self._seq += 1
            p = PlayerState(id=pid, name=name, seq=self._seq)
            self.players[pid] = p
            if self.host_id is None:
                self.host_id = pid
            # The REST join happens before the socket opens: keep the seat for a while.
            self._schedule(f"grace:{pid}", self.settings.lobby_grace_seconds, self._grace_expired, pid)
            await self._broadcast(msg("player_joined", player=self._public(p)), exclude=pid)
            return p

    async def connect(self, pid: int, ws: Any) -> None:
        async with self.lock:
            p = self.players.get(pid)
            if p is None or p.left or self.closed:
                await self._close_ws(ws, 4401)
                return
            old = p.ws
            was_connected = p.connected
            p.ws = ws
            p.connected = True
            self._cancel(f"grace:{pid}")
            self._cancel(f"drawer:{pid}")
            if old is not None and old is not ws:
                await self._close_ws(old, 4409)  # replaced by a newer connection
            await self._send(p, msg("state_sync", **self.snapshot(pid)))
            if not was_connected:
                await self._broadcast(msg("player_connected", player_id=pid, name=p.name), exclude=pid)

    async def disconnect(self, pid: int, ws: Any) -> None:
        async with self.lock:
            p = self.players.get(pid)
            if p is None or p.ws is not ws:
                return  # stale socket (replaced, or player already removed)
            p.ws = None
            p.connected = False
            await self._broadcast(msg("player_disconnected", player_id=pid, name=p.name))
            if self.phase == Phase.LOBBY:
                self._schedule(f"grace:{pid}", self.settings.lobby_grace_seconds, self._grace_expired, pid)
                return
            if self.phase == Phase.FINISHED:
                return
            self._schedule(f"grace:{pid}", self.settings.reconnect_grace_seconds, self._grace_expired, pid)
            r = self.round
            if self.phase == Phase.DRAWING and r is not None:
                if r.drawer_id == pid:
                    self._schedule(
                        f"drawer:{pid}", self.settings.drawer_grace_seconds, self._drawer_grace_expired, pid, r.number
                    )
                else:
                    await self._maybe_end_all_guessed()

    async def remove_player(self, pid: int, reason: str = "left") -> None:
        async with self.lock:
            p = self.players.get(pid)
            if p is None or p.left:
                return
            if self.phase == Phase.LOBBY:
                await self._remove_lobby_player(pid, reason)
            else:
                await self._mark_left(pid, reason)

    async def _grace_expired(self, pid: int) -> None:
        p = self.players.get(pid)
        if p is None or p.connected or p.left:
            return
        if self.phase == Phase.LOBBY:
            await self._remove_lobby_player(pid, "timeout")
        else:
            await self._mark_left(pid, "timeout")

    async def _drawer_grace_expired(self, pid: int, number: int) -> None:
        r = self.round
        p = self.players.get(pid)
        if self.phase == Phase.DRAWING and r is not None and r.number == number and p and not p.connected:
            await self._end_round("drawer_disconnected")

    async def _reassign_host(self) -> None:
        host = self.players.get(self.host_id) if self.host_id is not None else None
        if host is not None and not host.left:
            return
        candidates = self.connected_players() or self.active_players()
        if candidates:
            self.host_id = candidates[0].id
            await self._broadcast(msg("host_changed", host_id=self.host_id))

    async def _remove_lobby_player(self, pid: int, reason: str) -> None:
        p = self.players.pop(pid, None)
        if p is None:
            return
        self._cancel(f"grace:{pid}")
        await self._db(persistence.mark_player_left, pid)
        ws, p.ws, p.connected = p.ws, None, False
        await self._broadcast(msg("player_left", player_id=pid, name=p.name, reason=reason))
        if ws is not None:
            await self._close_ws(ws)
        if not self.players:
            await self._abandon()
        else:
            await self._reassign_host()

    async def _mark_left(self, pid: int, reason: str) -> None:
        p = self.players.get(pid)
        if p is None or p.left:
            return
        self._cancel(f"grace:{pid}")
        self._cancel(f"drawer:{pid}")
        p.left = True
        ws, p.ws, p.connected = p.ws, None, False
        await self._db(persistence.mark_player_left, pid)
        await self._broadcast(msg("player_left", player_id=pid, name=p.name, reason=reason))
        if ws is not None:
            await self._close_ws(ws)
        await self._reassign_host()
        r = self.round
        if self.phase == Phase.DRAWING and r is not None:
            if r.drawer_id == pid:
                await self._end_round("drawer_left")
            else:
                await self._maybe_end_all_guessed()
        if self.phase in (Phase.DRAWING, Phase.ROUND_END) and len(self.active_players()) < self.settings.min_players:
            await self._finish_game("not_enough_players")

    async def _abandon(self) -> None:
        self.phase = self.phase  # unchanged; room is simply discarded
        self.closed = True
        self._cancel_all()
        await self._db(persistence.set_room_status, self.db_id, "abandoned")
        self.manager.rooms.pop(self.code, None)

    async def _cleanup(self) -> None:
        self.closed = True
        for p in list(self.players.values()):
            if p.ws is not None:
                await self._close_ws(p.ws)
                p.ws = None
        self.manager.rooms.pop(self.code, None)

    # ----------------------------------------------------------------- dispatch
    async def handle_message(self, pid: int, raw: dict) -> None:
        mtype = raw.get("type")
        payload = raw.get("payload") or {}
        if not isinstance(payload, dict):
            await self._send_error(pid, "invalid_payload", "Payload must be an object.")
            return
        if mtype == "leave":
            await self.remove_player(pid, "left")
            return
        try:
            async with self.lock:
                p = self.players.get(pid)
                if p is None or p.left:
                    raise GameError("not_in_room", "You are not part of this room.")
                if mtype == "ping":
                    await self._send(p, msg("pong"))
                elif mtype == "ready":
                    await self._set_ready(p, ReadyPayload(**payload).ready)
                elif mtype == "start_game":
                    await self._start_game(p)
                elif mtype == "stroke":
                    await self._handle_stroke(p, StrokePayload(**payload))
                elif mtype == "clear_canvas":
                    await self._handle_clear(p)
                elif mtype == "guess":
                    await self._handle_guess(p, GuessPayload(**payload))
                else:
                    raise GameError("unknown_event", f"Unknown event type: {str(mtype)[:40]!r}")
        except ValidationError:
            await self._send_error(pid, "invalid_payload", "Invalid payload for this event.")
        except GameError as e:
            await self._send_error(pid, e.code, e.message)

    # ------------------------------------------------------------------ lobby
    async def _set_ready(self, p: PlayerState, ready: bool) -> None:
        if self.phase != Phase.LOBBY:
            raise GameError("not_in_lobby", "Readiness can only be changed in the lobby.")
        p.ready = ready
        await self._broadcast(msg("player_ready", player_id=p.id, ready=p.ready or p.id == self.host_id))

    async def _start_game(self, p: PlayerState) -> None:
        if p.id != self.host_id:
            raise GameError("not_host", "Only the host can start the game.")
        if self.phase != Phase.LOBBY:
            raise GameError("already_started", "The game has already started.")
        connected = self.connected_players()
        if len(connected) < self.settings.min_players:
            raise GameError(
                "not_enough_players", f"At least {self.settings.min_players} connected players are needed."
            )
        waiting = [q.name for q in connected if q.id != self.host_id and not q.ready]
        if waiting:
            raise GameError("players_not_ready", "Waiting for: " + ", ".join(waiting))
        await self._db(persistence.start_game, self.db_id)
        await self._broadcast(
            msg("game_started", total_rounds=self.total_rounds, players=[self._public(q) for q in self.players.values()])
        )
        await self._start_round()

    # ------------------------------------------------------------------ rounds
    async def _start_round(self) -> None:
        self.round_number += 1
        order = [p.id for p in sorted(self.players.values(), key=lambda q: q.seq)]
        eligible = {p.id for p in self.connected_players()}
        drawer = rules.pick_next_drawer(order, eligible, self.last_drawer_id)
        if drawer is None:
            self.round_number -= 1
            await self._finish_game("not_enough_players")
            return
        word = pick_word(self.used_words)
        self.used_words.add(word)
        self.last_drawer_id = drawer
        r = RoundState(
            number=self.round_number,
            drawer_id=drawer,
            word=word,
            duration=self.settings.round_seconds,
            started=self._now(),
        )
        self.round = r
        self.phase = Phase.DRAWING
        r.db_id = await self._db(persistence.create_round, self.db_id, r.number, drawer, word)
        await self._db(persistence.set_current_round, self.db_id, r.number)
        hint = rules.mask_word(word)
        drawer_name = self.players[drawer].name
        for p in self.connected_players():
            data = dict(
                round_number=r.number,
                total_rounds=self.total_rounds,
                drawer_id=drawer,
                drawer_name=drawer_name,
                hint=hint,
                round_seconds=r.duration,
                remaining=math.ceil(r.duration),
                players=[self._public(q) for q in self.players.values()],
            )
            if p.id == drawer:
                data["word"] = word  # private to the drawer
            await self._send(p, msg("round_started", **data))
        self._cancel("ticker")
        self._timers["ticker"] = asyncio.get_running_loop().create_task(self._tick_loop(r.number))

    async def _tick_loop(self, number: int) -> None:
        me = asyncio.current_task()
        try:
            while True:
                r = self.round
                if self.closed or self.phase != Phase.DRAWING or r is None or r.number != number:
                    return
                await asyncio.sleep(max(0.0, min(1.0, r.remaining(self._now()))))
                async with self.lock:
                    r = self.round
                    if self.closed or self.phase != Phase.DRAWING or r is None or r.number != number:
                        return
                    remaining = r.remaining(self._now())
                    if remaining <= 0:
                        await self._end_round("time_up")
                        return
                    await self._broadcast(msg("timer", round_number=number, remaining=math.ceil(remaining)))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("ticker failed")
        finally:
            if self._timers.get("ticker") is me:
                self._timers.pop("ticker", None)

    async def _maybe_end_all_guessed(self) -> None:
        r = self.round
        if self.phase != Phase.DRAWING or r is None:
            return
        guessers = [p for p in self.connected_players() if p.id != r.drawer_id]
        if guessers and all(p.id in r.guessed for p in guessers):
            await self._end_round("all_guessed")

    async def _end_round(self, reason: str) -> None:
        r = self.round
        if self.phase != Phase.DRAWING or r is None:
            return
        self._cancel("ticker")
        self._cancel_prefix("drawer:")
        self.phase = Phase.ROUND_END
        self.rounds_completed += 1
        results = [
            {
                "player_id": p.id,
                "name": p.name,
                "points_gained": r.gained.get(p.id, 0),
                "guessed": p.id in r.guessed,
                "is_drawer": p.id == r.drawer_id,
            }
            for p in self.players.values()
        ]
        scores = {p.id: p.score for p in self.players.values()}
        if r.db_id is not None:
            await self._db(persistence.end_round, r.db_id, scores)
        payload = dict(
            reason=reason,
            word=r.word,  # revealed to everyone now that the round is over
            round_number=r.number,
            total_rounds=self.total_rounds,
            results=results,
            scores=self._scores_payload(),
            next_in=self.settings.result_seconds,
            is_last=r.number >= self.total_rounds,
        )
        self.last_result = payload
        await self._broadcast(msg("round_ended", **payload))
        self._schedule("result", self.settings.result_seconds, self._after_result, r.number)

    async def _after_result(self, number: int) -> None:
        if self.phase != Phase.ROUND_END or self.round_number != number:
            return
        if number >= self.total_rounds:
            await self._finish_game("completed")
            return
        if len(self.active_players()) < self.settings.min_players:
            await self._finish_game("not_enough_players")
            return
        if len(self.connected_players()) < self.settings.min_players:
            # Wait for reconnects; grace timers guarantee this cannot last forever.
            await self._broadcast(msg("waiting_for_players", needed=self.settings.min_players))
            self._schedule("result", 2.0, self._after_result, number)
            return
        await self._start_round()  # clears canvas for everyone via round_started

    async def _finish_game(self, reason: str) -> None:
        if self.phase == Phase.FINISHED:
            return
        self._cancel_all(keep=("cleanup",))
        self.phase = Phase.FINISHED
        board = rules.rank_leaderboard([(p.id, p.name, p.score) for p in self.players.values()])
        self.leaderboard = board
        winners = [e["player_id"] for e in board if e["is_winner"]]
        status = "finished" if self.rounds_completed > 0 else "abandoned"
        await self._db(
            persistence.finish_game, self.db_id, status, {p.id: p.score for p in self.players.values()}, winners
        )
        await self._broadcast(msg("game_ended", reason=reason, leaderboard=board))
        self._schedule("cleanup", self.settings.finished_room_ttl_seconds, self._cleanup)

    # ------------------------------------------------------------ drawing/guess
    def _require_drawer(self, p: PlayerState) -> RoundState:
        r = self.round
        if self.phase != Phase.DRAWING or r is None or r.remaining(self._now()) <= 0:
            raise GameError("round_inactive", "There is no active round.")
        if r.drawer_id != p.id:
            raise GameError("not_drawer", "Only the drawer can draw.")
        return r

    async def _handle_stroke(self, p: PlayerState, data: StrokePayload) -> None:
        r = self._require_drawer(p)
        pts = [[x, y] for x, y in data.points]
        s = r.stroke_index.get(data.stroke_id)
        if s is None:
            s = {"id": data.stroke_id, "tool": data.tool, "color": data.color, "size": data.size, "points": []}
            r.strokes.append(s)
            r.stroke_index[data.stroke_id] = s
        if r.point_count + len(pts) <= self.settings.max_stroke_points_stored:
            s["points"].extend(pts)
            r.point_count += len(pts)
        await self._broadcast(
            msg(
                "stroke",
                stroke_id=data.stroke_id,
                tool=data.tool,
                color=data.color,
                size=data.size,
                points=pts,
                end=data.end,
            ),
            exclude=p.id,
        )

    async def _handle_clear(self, p: PlayerState) -> None:
        r = self._require_drawer(p)
        r.strokes.clear()
        r.stroke_index.clear()
        r.point_count = 0
        await self._broadcast(msg("canvas_cleared"), exclude=p.id)

    async def _handle_guess(self, p: PlayerState, data: GuessPayload) -> None:
        r = self.round
        now = self._now()
        if self.phase != Phase.DRAWING or r is None or r.remaining(now) <= 0:
            raise GameError("round_inactive", "The round is not active.")
        if p.id == r.drawer_id:
            raise GameError("drawer_cannot_guess", "The drawer cannot submit guesses.")
        if p.id in r.guessed:
            raise GameError("already_guessed", "You already guessed this word.")
        correct = rules.is_correct_guess(data.text, r.word)
        if r.db_id is not None:
            await self._db(persistence.record_guess, r.db_id, p.id, data.text, correct)
        if not correct:
            await self._broadcast(msg("chat", player_id=p.id, name=p.name, text=data.text))
            return
        pts = rules.guesser_points(r.remaining(now), r.duration, r.number)
        p.score += pts
        r.guessed[p.id] = pts
        r.gained[p.id] = r.gained.get(p.id, 0) + pts
        drawer = self.players[r.drawer_id]
        dpts = rules.drawer_points(1, r.number)
        drawer.score += dpts
        r.gained[drawer.id] = r.gained.get(drawer.id, 0) + dpts
        await self._db(persistence.update_scores, {p.id: p.score, drawer.id: drawer.score})
        # The guess text is deliberately NOT broadcast.
        await self._broadcast(
            msg("correct_guess", player_id=p.id, name=p.name, points=pts, order=len(r.guessed))
        )
        await self._broadcast(msg("scores_updated", scores=self._scores_payload()))
        await self._maybe_end_all_guessed()
