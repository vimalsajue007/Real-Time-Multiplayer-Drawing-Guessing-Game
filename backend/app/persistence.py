"""Synchronous persistence functions. Each takes a Session as its first argument
and is executed through DbRunner (see database.py)."""
from __future__ import annotations

from sqlalchemy import select, update

from .models import GameRoom, GameRound, Guess, Player, utcnow


def create_room(s, code: str, total_rounds: int) -> int:
    room = GameRoom(room_code=code, status="waiting", current_round=0, total_rounds=total_rounds)
    s.add(room)
    s.flush()
    return room.id


def add_player(s, room_id: int, name: str) -> int:
    p = Player(room_id=room_id, display_name=name)
    s.add(p)
    s.flush()
    return p.id


def mark_player_left(s, player_id: int) -> None:
    p = s.get(Player, player_id)
    if p and p.left_at is None:
        p.left_at = utcnow()


def start_game(s, room_id: int) -> None:
    room = s.get(GameRoom, room_id)
    room.status = "in_progress"
    room.started_at = utcnow()


def create_round(s, room_id: int, number: int, drawer_id: int, word: str) -> int:
    rd = GameRound(room_id=room_id, round_number=number, drawer_player_id=drawer_id, word=word)
    s.add(rd)
    s.flush()
    return rd.id


def set_current_round(s, room_id: int, number: int) -> None:
    s.get(GameRoom, room_id).current_round = number


def record_guess(s, round_id: int, player_id: int, text: str, is_correct: bool) -> None:
    s.add(Guess(round_id=round_id, player_id=player_id, guess_text=text[:128], is_correct=is_correct))


def update_scores(s, scores: dict[int, int]) -> None:
    for pid, score in scores.items():
        s.execute(update(Player).where(Player.id == pid).values(score=score))


def end_round(s, round_id: int, scores: dict[int, int]) -> None:
    rd = s.get(GameRound, round_id)
    if rd:
        rd.ended_at = utcnow()
    update_scores(s, scores)


def finish_game(s, room_id: int, status: str, scores: dict[int, int], winner_ids: list[int]) -> None:
    room = s.get(GameRoom, room_id)
    room.status = status
    room.ended_at = utcnow()
    now = utcnow()
    for p in room.players:
        if p.id in scores:
            p.score = scores[p.id]
        p.is_winner = p.id in winner_ids
        if p.left_at is None:
            p.left_at = now


def set_room_status(s, room_id: int, status: str) -> None:
    room = s.get(GameRoom, room_id)
    room.status = status
    if status in ("finished", "abandoned"):
        room.ended_at = utcnow()


def abandon_stale_rooms(s) -> int:
    """Rooms left over from a previous server run can never resume (state is in memory)."""
    rooms = s.scalars(select(GameRoom).where(GameRoom.status.in_(["waiting", "in_progress"]))).all()
    for r in rooms:
        r.status = "abandoned"
        r.ended_at = utcnow()
    return len(rooms)


def room_status(s, code: str) -> str | None:
    return s.scalar(select(GameRoom.status).where(GameRoom.room_code == code))


def code_exists(s, code: str) -> bool:
    return s.scalar(select(GameRoom.id).where(GameRoom.room_code == code)) is not None
