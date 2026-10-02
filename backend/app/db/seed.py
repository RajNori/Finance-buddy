"""Lazy schema creation and default seed data."""

from __future__ import annotations

import logging

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from .schema import DEFAULT_USER, metadata, new_id, users_profile, utcnow, watchlist

logger = logging.getLogger(__name__)

DEFAULT_CASH = 10_000.0
DEFAULT_WATCHLIST = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def init_db(engine: Engine) -> bool:
    """Create missing tables and seed the default user. Idempotent.

    Returns True if seed data was inserted (fresh database).
    """
    metadata.create_all(engine)

    with engine.begin() as conn:
        exists = conn.execute(
            select(users_profile.c.id).where(users_profile.c.id == DEFAULT_USER)
        ).first()
        if exists:
            return False

        now = utcnow()
        conn.execute(
            insert(users_profile).values(id=DEFAULT_USER, cash_balance=DEFAULT_CASH, created_at=now)
        )
        conn.execute(
            insert(watchlist),
            [
                {"id": new_id(), "user_id": DEFAULT_USER, "ticker": t, "added_at": now}
                for t in DEFAULT_WATCHLIST
            ],
        )

    logger.info("Seeded fresh database with default user and watchlist")
    return True
