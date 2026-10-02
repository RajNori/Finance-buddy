"""Table definitions (PLAN.md §7). Types are portable: no SQLite-only features.

Timestamps are ISO-8601 UTC strings, which sort correctly as text.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, Float, Index, MetaData, String, Table, Text, UniqueConstraint

DEFAULT_USER = "default"

metadata = MetaData()


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


users_profile = Table(
    "users_profile",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("cash_balance", Float, nullable=False),
    Column("created_at", String(32), nullable=False),
)

watchlist = Table(
    "watchlist",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), nullable=False, default=DEFAULT_USER),
    Column("ticker", String(16), nullable=False),
    Column("added_at", String(32), nullable=False),
    UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
)

positions = Table(
    "positions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), nullable=False, default=DEFAULT_USER),
    Column("ticker", String(16), nullable=False),
    Column("quantity", Float, nullable=False),
    Column("avg_cost", Float, nullable=False),
    Column("updated_at", String(32), nullable=False),
    UniqueConstraint("user_id", "ticker", name="uq_positions_user_ticker"),
)

trades = Table(
    "trades",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), nullable=False, default=DEFAULT_USER),
    Column("ticker", String(16), nullable=False),
    Column("side", String(4), nullable=False),
    Column("quantity", Float, nullable=False),
    Column("price", Float, nullable=False),
    Column("executed_at", String(32), nullable=False),
    Index("ix_trades_user_executed", "user_id", "executed_at"),
)

portfolio_snapshots = Table(
    "portfolio_snapshots",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), nullable=False, default=DEFAULT_USER),
    Column("total_value", Float, nullable=False),
    Column("recorded_at", String(32), nullable=False),
    Index("ix_snapshots_user_recorded", "user_id", "recorded_at"),
)

chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(64), nullable=False, default=DEFAULT_USER),
    Column("role", String(16), nullable=False),
    Column("content", Text, nullable=False),
    Column("actions", Text, nullable=True),  # JSON
    Column("created_at", String(32), nullable=False),
    Index("ix_chat_user_created", "user_id", "created_at"),
)
