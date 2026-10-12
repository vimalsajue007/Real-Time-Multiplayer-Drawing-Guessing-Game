from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from . import persistence
from .config import Settings, get_settings
from .database import DbRunner, make_engine, make_session_factory
from .game.errors import GameError
from .game.manager import GameManager
from .routers import rooms, stats, ws

DESCRIPTION = """
Real-time multiplayer drawing & guessing game.

* **REST** (this page): create/join/leave rooms, room info, history, leaderboard, player stats.
* **WebSocket** `/ws/{room_code}?token=...`: all real-time gameplay. Swagger cannot render
  WebSockets - see **GET /api/protocol** and the README for the full event reference.
"""


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or make_engine(settings.database_url)
    db = DbRunner(make_session_factory(engine))
    manager = GameManager(settings, db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # In-memory games do not survive a restart, so close any stale rooms.
        await db.run(persistence.abandon_stale_rooms)
        yield
        await manager.shutdown()

    app = FastAPI(title="Draw & Guess API", version="1.0.0", description=DESCRIPTION, lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.manager = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(GameError)
    async def game_error_handler(_: Request, exc: GameError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code})

    app.include_router(rooms.router)
    app.include_router(stats.router)
    app.include_router(ws.router)
    return app


app = create_app()
