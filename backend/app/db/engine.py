"""Engine construction from DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url

# backend/app/db/engine.py -> repo root. In the container DATABASE_URL is set
# explicitly (see Dockerfile), so this default only applies to local runs.
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = REPO_ROOT / "db" / "financebuddy.db"


def database_url() -> str:
    """DATABASE_URL if set, else the local SQLite file."""
    return os.environ.get("DATABASE_URL", "").strip() or f"sqlite:///{DEFAULT_SQLITE_PATH}"


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    parsed = make_url(url)

    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        # SQLite-only tuning, applied per connection. Shared code stays portable.
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        return engine

    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
