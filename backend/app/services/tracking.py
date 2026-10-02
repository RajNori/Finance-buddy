"""Keeps the market data source tracking exactly: watchlist ∪ held positions.

A held position must keep receiving prices even after it is removed from the
watchlist, otherwise it could not be valued or sold.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from app.market import MarketDataSource

from .portfolio import held_tickers
from .watchlist import watchlist_tickers


def tracked_tickers(engine: Engine) -> list[str]:
    watched = watchlist_tickers(engine)
    extra = sorted(held_tickers(engine) - set(watched))
    return watched + extra


async def sync_ticker(engine: Engine, source: MarketDataSource, ticker: str) -> None:
    """Start or stop price updates for one ticker to match the database."""

    def should_track() -> bool:
        return ticker in watchlist_tickers(engine) or ticker in held_tickers(engine)

    wanted = await run_in_threadpool(should_track)
    tracked = ticker in source.get_tickers()
    if wanted and not tracked:
        await source.add_ticker(ticker)
    elif not wanted and tracked:
        await source.remove_ticker(ticker)
