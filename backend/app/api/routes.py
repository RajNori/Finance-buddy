"""Portfolio and watchlist REST endpoints (PLAN.md §8)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.services import portfolio as portfolio_svc
from app.services import watchlist as watchlist_svc
from app.services.tracking import sync_ticker

router = APIRouter(prefix="/api")


class TradeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    quantity: float
    side: Literal["buy", "sell"]


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


# --- Portfolio --------------------------------------------------------------


@router.get("/portfolio", tags=["portfolio"])
async def get_portfolio(request: Request) -> dict:
    state = request.app.state
    return await run_in_threadpool(portfolio_svc.get_portfolio, state.engine, state.price_cache)


@router.post("/portfolio/trade", tags=["portfolio"])
async def trade(body: TradeRequest, request: Request) -> dict:
    state = request.app.state
    result = await run_in_threadpool(
        portfolio_svc.execute_trade,
        state.engine,
        state.price_cache,
        body.ticker,
        body.side,
        body.quantity,
    )
    if result.position_quantity == 0:
        # Closed a position: stop pricing it unless it's still watched.
        await sync_ticker(state.engine, state.market_source, result.ticker)
    return {"trade": result.to_dict()}


@router.get("/portfolio/history", tags=["portfolio"])
async def portfolio_history(request: Request) -> dict:
    snapshots = await run_in_threadpool(portfolio_svc.get_history, request.app.state.engine)
    return {"snapshots": snapshots}


# --- Watchlist --------------------------------------------------------------


@router.get("/watchlist", tags=["watchlist"])
async def get_watchlist(request: Request) -> dict:
    state = request.app.state
    items = await run_in_threadpool(watchlist_svc.get_watchlist, state.engine, state.price_cache)
    return {"tickers": items}


@router.post("/watchlist", tags=["watchlist"])
async def add_to_watchlist(body: WatchlistAddRequest, request: Request) -> dict:
    state = request.app.state
    ticker, added = await run_in_threadpool(watchlist_svc.add_ticker, state.engine, body.ticker)
    await sync_ticker(state.engine, state.market_source, ticker)
    return {"ticker": ticker, "added": added}


@router.delete("/watchlist/{ticker}", tags=["watchlist"])
async def remove_from_watchlist(ticker: str, request: Request) -> dict:
    state = request.app.state
    removed = await run_in_threadpool(watchlist_svc.remove_ticker, state.engine, ticker)
    await sync_ticker(state.engine, state.market_source, removed)
    return {"ticker": removed, "removed": True}
