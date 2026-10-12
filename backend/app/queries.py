"""Read-side queries used by the REST API."""
from __future__ import annotations

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import selectinload

from .models import GameRoom, GameRound, Guess, Player


def _wins_expr():
    return func.coalesce(func.sum(case((Player.is_winner.is_(True), 1), else_=0)), 0)


def leaderboard(s, limit: int) -> list[dict]:
    stmt = (
        select(
            func.min(Player.display_name).label("display_name"),
            func.sum(Player.score).label("total_score"),
            func.count(Player.id).label("games_played"),
            _wins_expr().label("wins"),
            func.max(Player.score).label("best_score"),
        )
        .join(GameRoom, GameRoom.id == Player.room_id)
        .where(GameRoom.status == "finished")
        .group_by(func.lower(Player.display_name))
        .order_by(desc("total_score"), desc("wins"))
        .limit(limit)
    )
    rows = s.execute(stmt).all()
    return [
        {
            "rank": i + 1,
            "display_name": r.display_name,
            "total_score": int(r.total_score or 0),
            "games_played": int(r.games_played),
            "wins": int(r.wins or 0),
            "best_score": int(r.best_score or 0),
        }
        for i, r in enumerate(rows)
    ]


def player_stats(s, name: str) -> dict | None:
    key = name.strip().lower()
    row = s.execute(
        select(
            func.min(Player.display_name).label("display_name"),
            func.sum(Player.score).label("total_score"),
            func.count(Player.id).label("games_played"),
            _wins_expr().label("wins"),
            func.max(Player.score).label("best_score"),
        )
        .join(GameRoom, GameRoom.id == Player.room_id)
        .where(GameRoom.status == "finished", func.lower(Player.display_name) == key)
    ).one()
    if not row.games_played:
        return None
    correct = s.scalar(
        select(func.count(Guess.id))
        .join(Player, Player.id == Guess.player_id)
        .join(GameRoom, GameRoom.id == Player.room_id)
        .where(GameRoom.status == "finished", func.lower(Player.display_name) == key, Guess.is_correct.is_(True))
    )
    drawn = s.scalar(
        select(func.count(GameRound.id))
        .join(Player, Player.id == GameRound.drawer_player_id)
        .join(GameRoom, GameRoom.id == GameRound.room_id)
        .where(GameRoom.status == "finished", func.lower(Player.display_name) == key)
    )
    games = int(row.games_played)
    total = int(row.total_score or 0)
    wins = int(row.wins or 0)
    return {
        "display_name": row.display_name,
        "games_played": games,
        "wins": wins,
        "win_rate": round(wins / games, 3),
        "total_score": total,
        "average_score": round(total / games, 1),
        "best_score": int(row.best_score or 0),
        "correct_guesses": int(correct or 0),
        "rounds_drawn": int(drawn or 0),
    }


def _players_payload(room: GameRoom) -> list[dict]:
    ps = sorted(room.players, key=lambda p: p.score, reverse=True)
    return [{"display_name": p.display_name, "score": p.score, "is_winner": bool(p.is_winner)} for p in ps]


def game_history(s, limit: int, offset: int) -> list[dict]:
    rooms = s.scalars(
        select(GameRoom)
        .where(GameRoom.status == "finished")
        .order_by(GameRoom.ended_at.desc(), GameRoom.id.desc())
        .limit(limit)
        .offset(offset)
        .options(selectinload(GameRoom.players))
    ).all()
    return [
        {
            "room_code": r.room_code,
            "status": r.status,
            "total_rounds": r.total_rounds,
            "started_at": r.started_at,
            "ended_at": r.ended_at,
            "players": _players_payload(r),
        }
        for r in rooms
    ]


def game_detail(s, code: str) -> dict | None:
    room = s.scalar(
        select(GameRoom)
        .where(GameRoom.room_code == code)
        .options(selectinload(GameRoom.players), selectinload(GameRoom.rounds).selectinload(GameRound.guesses))
    )
    if room is None:
        return None
    names = {p.id: p.display_name for p in room.players}
    rounds = [
        {
            "round_number": rd.round_number,
            "drawer": names.get(rd.drawer_player_id),
            "word": rd.word,
            "started_at": rd.started_at,
            "ended_at": rd.ended_at,
            "correct_guesses": sum(1 for g in rd.guesses if g.is_correct),
            "total_guesses": len(rd.guesses),
        }
        for rd in room.rounds
    ]
    return {
        "room_code": room.room_code,
        "status": room.status,
        "current_round": room.current_round,
        "total_rounds": room.total_rounds,
        "created_at": room.created_at,
        "started_at": room.started_at,
        "ended_at": room.ended_at,
        "players": _players_payload(room),
        "rounds": rounds,
    }


def room_summary_from_db(s, code: str) -> dict | None:
    room = s.scalar(select(GameRoom).where(GameRoom.room_code == code).options(selectinload(GameRoom.players)))
    if room is None:
        return None
    return {
        "room_code": room.room_code,
        "status": room.status,
        "joinable": False,
        "player_count": len(room.players),
        "total_rounds": room.total_rounds,
        "current_round": room.current_round,
        "players": [{"display_name": p.display_name, "score": p.score} for p in room.players],
    }
