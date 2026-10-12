import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Base, DbRunner, make_engine, make_session_factory
from app.game.manager import GameManager
from app.main import create_app


def make_settings(**overrides) -> Settings:
    base = dict(
        database_url="sqlite://",
        secret_key="test-secret",
        round_seconds=30,
        result_seconds=0.3,
        drawer_grace_seconds=0.4,
        reconnect_grace_seconds=1.0,
        lobby_grace_seconds=5,
        finished_room_ttl_seconds=5,
        min_players=2,
        max_players=4,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def engine():
    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def client(settings, engine):
    app = create_app(settings, engine)
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def manager(settings, engine):
    mgr = GameManager(settings, DbRunner(make_session_factory(engine)))
    yield mgr
    await mgr.shutdown()
