"""Database layer: SQLAlchemy Core, portable across SQLite (local) and Postgres (AWS)."""

from .engine import database_url, make_engine
from .schema import (
    DEFAULT_USER,
    chat_messages,
    metadata,
    portfolio_snapshots,
    positions,
    trades,
    users_profile,
    watchlist,
)
from .seed import DEFAULT_CASH, DEFAULT_WATCHLIST, init_db

__all__ = [
    "DEFAULT_CASH",
    "DEFAULT_USER",
    "DEFAULT_WATCHLIST",
    "chat_messages",
    "database_url",
    "init_db",
    "make_engine",
    "metadata",
    "portfolio_snapshots",
    "positions",
    "trades",
    "users_profile",
    "watchlist",
]
