"""Watchlist reads and writes."""

from __future__ import annotations

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.db.schema import DEFAULT_USER, new_id, utcnow, watchlist
from app.market import PriceCache

from .portfolio import normalize_ticker


class TickerNotFoundError(LookupError):
    pass


def watchlist_tickers(engine: Engine, user_id: str = DEFAULT_USER) -> list[str]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(watchlist.c.ticker)
                .where(watchlist.c.user_id == user_id)
                .order_by(watchlist.c.added_at, watchlist.c.ticker)
            ).scalars()
        )


def get_watchlist(engine: Engine, cache: PriceCache, user_id: str = DEFAULT_USER) -> list[dict]:
    """Watched tickers with their latest price data (None until the first tick)."""
    items = []
    for ticker in watchlist_tickers(engine, user_id):
        update = cache.get(ticker)
        if update is None:
            items.append({"ticker": ticker, "price": None})
        else:
            items.append(update.to_dict())
    return items


def add_ticker(engine: Engine, raw_ticker: str, user_id: str = DEFAULT_USER) -> tuple[str, bool]:
    """Add a ticker. Idempotent. Returns (ticker, added) where added=False if already present."""
    ticker = normalize_ticker(raw_ticker)
    try:
        with engine.begin() as conn:
            conn.execute(
                insert(watchlist).values(
                    id=new_id(), user_id=user_id, ticker=ticker, added_at=utcnow()
                )
            )
    except IntegrityError:
        return ticker, False
    return ticker, True


def remove_ticker(engine: Engine, raw_ticker: str, user_id: str = DEFAULT_USER) -> str:
    ticker = normalize_ticker(raw_ticker)
    with engine.begin() as conn:
        result = conn.execute(
            delete(watchlist).where(watchlist.c.user_id == user_id, watchlist.c.ticker == ticker)
        )
    if result.rowcount == 0:
        raise TickerNotFoundError(f"{ticker} is not on the watchlist")
    return ticker
