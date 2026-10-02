"""Portfolio valuation, trade execution and snapshots.

All functions are synchronous and take an Engine; the API layer runs them in
a threadpool. Each trade is one transaction: cash, position, trade log and a
snapshot commit together or not at all.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.db.schema import (
    DEFAULT_USER,
    new_id,
    portfolio_snapshots,
    positions,
    trades,
    users_profile,
    utcnow,
)
from app.market import PriceCache

TICKER_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")
QTY_DECIMALS = 6
QTY_EPSILON = 10**-QTY_DECIMALS
HISTORY_LIMIT = 2880  # 48h of 60s snapshots


class TradeError(ValueError):
    """A trade failed validation. The message is safe to show the user."""


class InvalidTickerError(ValueError):
    """Ticker symbol is malformed."""


def normalize_ticker(raw: str) -> str:
    ticker = (raw or "").strip().upper()
    if not TICKER_RE.fullmatch(ticker):
        raise InvalidTickerError(f"Invalid ticker symbol: {raw!r}")
    return ticker


@dataclass(frozen=True)
class TradeResult:
    ticker: str
    side: str
    quantity: float
    price: float
    total: float
    cash_balance: float
    position_quantity: float  # remaining after the trade; 0 when closed

    def to_dict(self) -> dict:
        return asdict(self)


# --- Reads ------------------------------------------------------------------


def _held_positions(conn: Connection, user_id: str) -> list:
    return conn.execute(
        select(positions).where(positions.c.user_id == user_id).order_by(positions.c.ticker)
    ).all()


def _total_value(conn: Connection, cache: PriceCache, user_id: str, cash: float) -> float:
    total = cash
    for row in _held_positions(conn, user_id):
        price = cache.get_price(row.ticker)
        total += row.quantity * (price if price is not None else row.avg_cost)
    return round(total, 2)


def held_tickers(engine: Engine, user_id: str = DEFAULT_USER) -> set[str]:
    with engine.connect() as conn:
        return {row.ticker for row in _held_positions(conn, user_id)}


def get_portfolio(engine: Engine, cache: PriceCache, user_id: str = DEFAULT_USER) -> dict:
    """Cash, positions with live P&L, and totals.

    A position with no live price is valued at cost (P&L 0) and flagged.
    """
    with engine.connect() as conn:
        cash = conn.execute(
            select(users_profile.c.cash_balance).where(users_profile.c.id == user_id)
        ).scalar_one()
        rows = _held_positions(conn, user_id)

    items = []
    invested = 0.0
    market_value_total = 0.0
    for row in rows:
        live = cache.get_price(row.ticker)
        price = live if live is not None else row.avg_cost
        cost_basis = row.quantity * row.avg_cost
        market_value = row.quantity * price
        pnl = market_value - cost_basis
        invested += cost_basis
        market_value_total += market_value
        items.append(
            {
                "ticker": row.ticker,
                "quantity": row.quantity,
                "avg_cost": round(row.avg_cost, 4),
                "current_price": price,
                "price_available": live is not None,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_percent": round(pnl / cost_basis * 100, 2) if cost_basis else 0.0,
            }
        )

    unrealized = market_value_total - invested
    return {
        "cash_balance": round(cash, 2),
        "positions": items,
        "positions_value": round(market_value_total, 2),
        "total_value": round(cash + market_value_total, 2),
        "unrealized_pnl": round(unrealized, 2),
        "unrealized_pnl_percent": round(unrealized / invested * 100, 2) if invested else 0.0,
    }


def get_history(
    engine: Engine, user_id: str = DEFAULT_USER, limit: int = HISTORY_LIMIT
) -> list[dict]:
    """Most recent snapshots, oldest first (ready to chart)."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(portfolio_snapshots.c.total_value, portfolio_snapshots.c.recorded_at)
            .where(portfolio_snapshots.c.user_id == user_id)
            .order_by(portfolio_snapshots.c.recorded_at.desc())
            .limit(limit)
        ).all()
    return [{"total_value": r.total_value, "recorded_at": r.recorded_at} for r in reversed(rows)]


# --- Writes -----------------------------------------------------------------


def _insert_snapshot(conn: Connection, user_id: str, total_value: float) -> None:
    conn.execute(
        insert(portfolio_snapshots).values(
            id=new_id(), user_id=user_id, total_value=total_value, recorded_at=utcnow()
        )
    )


def record_snapshot(engine: Engine, cache: PriceCache, user_id: str = DEFAULT_USER) -> float:
    with engine.begin() as conn:
        cash = conn.execute(
            select(users_profile.c.cash_balance).where(users_profile.c.id == user_id)
        ).scalar_one()
        total = _total_value(conn, cache, user_id, cash)
        _insert_snapshot(conn, user_id, total)
    return total


def execute_trade(
    engine: Engine,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER,
) -> TradeResult:
    """Market order at the current cached price. Raises TradeError on validation failure."""
    ticker = normalize_ticker(ticker)
    side = (side or "").strip().lower()
    if side not in ("buy", "sell"):
        raise TradeError(f"Side must be 'buy' or 'sell', got {side!r}")
    if not isinstance(quantity, int | float) or not math.isfinite(quantity):
        raise TradeError("Quantity must be a number")
    quantity = round(float(quantity), QTY_DECIMALS)
    if quantity <= 0:
        raise TradeError("Quantity must be greater than zero")

    price = cache.get_price(ticker)
    if price is None:
        raise TradeError(f"No live price for {ticker}. Add it to the watchlist first.")

    total = round(quantity * price, 2)
    now = utcnow()

    with engine.begin() as conn:
        # Row locks serialise concurrent trades on Postgres; SQLite ignores them
        # (its writer lock already serialises the transaction).
        cash = conn.execute(
            select(users_profile.c.cash_balance)
            .where(users_profile.c.id == user_id)
            .with_for_update()
        ).scalar_one()
        position = conn.execute(
            select(positions)
            .where(positions.c.user_id == user_id, positions.c.ticker == ticker)
            .with_for_update()
        ).first()
        held = position.quantity if position else 0.0

        if side == "buy":
            if total > cash:
                raise TradeError(
                    f"Insufficient cash to buy {quantity:g} {ticker}: "
                    f"need ${total:,.2f}, have ${cash:,.2f}"
                )
            new_cash = round(cash - total, 2)
            new_qty = round(held + quantity, QTY_DECIMALS)
            prior_cost = held * position.avg_cost if position else 0.0
            new_avg = (prior_cost + quantity * price) / new_qty
        else:
            if quantity > held + QTY_EPSILON:
                raise TradeError(
                    f"Insufficient shares to sell {quantity:g} {ticker}: you hold {held:g}"
                )
            new_cash = round(cash + total, 2)
            new_qty = round(held - quantity, QTY_DECIMALS)
            new_avg = position.avg_cost

        conn.execute(
            update(users_profile).where(users_profile.c.id == user_id).values(cash_balance=new_cash)
        )

        if new_qty <= QTY_EPSILON:
            new_qty = 0.0
            conn.execute(delete(positions).where(positions.c.id == position.id))
        elif position:
            conn.execute(
                update(positions)
                .where(positions.c.id == position.id)
                .values(quantity=new_qty, avg_cost=new_avg, updated_at=now)
            )
        else:
            conn.execute(
                insert(positions).values(
                    id=new_id(),
                    user_id=user_id,
                    ticker=ticker,
                    quantity=new_qty,
                    avg_cost=new_avg,
                    updated_at=now,
                )
            )

        conn.execute(
            insert(trades).values(
                id=new_id(),
                user_id=user_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=price,
                executed_at=now,
            )
        )
        _insert_snapshot(conn, user_id, _total_value(conn, cache, user_id, new_cash))

    return TradeResult(
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=price,
        total=total,
        cash_balance=new_cash,
        position_quantity=new_qty,
    )
