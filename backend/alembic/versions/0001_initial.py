"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_rooms",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("room_code", sa.String(8), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column("current_round", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_rounds", sa.Integer, nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("ended_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_game_rooms_room_code", "game_rooms", ["room_code"], unique=True)

    op.create_table(
        "players",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(32), nullable=False),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("joined_at", sa.DateTime, nullable=False),
        sa.Column("left_at", sa.DateTime, nullable=True),
        sa.Column("is_winner", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_players_room_id", "players", ["room_id"])
    op.create_index("ix_players_display_name", "players", ["display_name"])

    op.create_table(
        "game_rounds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("drawer_player_id", sa.Integer, sa.ForeignKey("players.id", ondelete="SET NULL"), nullable=True),
        sa.Column("word", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_game_rounds_room_id", "game_rounds", ["room_id"])

    op.create_table(
        "guesses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("round_id", sa.Integer, sa.ForeignKey("game_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guess_text", sa.String(128), nullable=False),
        sa.Column("is_correct", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("submitted_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_guesses_round_id", "guesses", ["round_id"])
    op.create_index("ix_guesses_player_id", "guesses", ["player_id"])


def downgrade() -> None:
    op.drop_table("guesses")
    op.drop_table("game_rounds")
    op.drop_table("players")
    op.drop_table("game_rooms")
