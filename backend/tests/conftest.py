"""Pytest configuration and fixtures."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
def _simulator_only(monkeypatch):
    """Tests never hit the real Massive API or a real DATABASE_URL."""
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture
def db_url(tmp_path):
    """SQLite by default. Set TEST_POSTGRES_URL to run the same suite on Postgres."""
    pg_url = os.environ.get("TEST_POSTGRES_URL")
    if not pg_url:
        yield f"sqlite:///{tmp_path / 'test.db'}"
        return

    from app.db import make_engine, metadata

    engine = make_engine(pg_url)
    metadata.drop_all(engine)
    engine.dispose()
    yield pg_url


@pytest.fixture
def engine(db_url):
    from app.db import init_db, make_engine

    engine = make_engine(db_url)
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(db_url):
    from app.main import create_app

    with TestClient(create_app(db_url, snapshot_interval=3600)) as c:
        yield c
