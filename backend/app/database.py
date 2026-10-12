"""SQLAlchemy engine/session helpers and the async-friendly DB runner."""
from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Callable

import anyio.to_thread
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class DbRunner:
    """Runs synchronous DB functions in a worker thread, one at a time.

    Each call gets its own Session (committed on success, rolled back on error).
    Serialising calls keeps ordering deterministic and makes SQLite-in-memory
    safe for tests.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory
        self._lock = asyncio.Lock()

    def _exec(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._sf() as session:
            try:
                result = fn(session, *args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise

    async def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            return await anyio.to_thread.run_sync(partial(self._exec, fn, *args, **kwargs))
