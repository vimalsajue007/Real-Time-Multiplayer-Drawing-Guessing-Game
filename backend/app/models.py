"""ORM models. Only durable game data is stored — never drawing strokes."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GameRoom(Base):
    __tablename__ = "game_rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="waiting")  # waiting|in_progress|finished|abandoned
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    total_rounds: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    players: Mapped[list["Player"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="Player.id"
    )
    rounds: Mapped[list["GameRound"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="GameRound.round_number"
    )


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (Index("ix_players_display_name", "display_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("game_rooms.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(32))
    score: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Additive column so winners are stored explicitly (ties => several winners).
    is_winner: Mapped[bool] = mapped_column(Boolean, default=False)

    room: Mapped[GameRoom] = relationship(back_populates="players")


class GameRound(Base):
    __tablename__ = "game_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("game_rooms.id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    drawer_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    word: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    room: Mapped[GameRoom] = relationship(back_populates="rounds")
    guesses: Mapped[list["Guess"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class Guess(Base):
    __tablename__ = "guesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("game_rounds.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    guess_text: Mapped[str] = mapped_column(String(128))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    round: Mapped[GameRound] = relationship(back_populates="guesses")
