"""Trade execution, valuation and snapshots (service layer, deterministic prices)."""

import pytest
from sqlalchemy import func, select

from app.db import portfolio_snapshots, positions, trades
from app.market import PriceCache
from app.services.portfolio import (
    InvalidTickerError,
    TradeError,
    execute_trade,
    get_history,
    get_portfolio,
    normalize_ticker,
    record_snapshot,
)


@pytest.fixture
def cache():
    cache = PriceCache()
    cache.update("AAPL", 100.0)
    cache.update("MSFT", 50.0)
    return cache


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


class TestBuy:
    def test_buy_debits_cash_and_opens_position(self, engine, cache):
        result = execute_trade(engine, cache, "aapl", "buy", 10)

        assert result.ticker == "AAPL"
        assert result.total == 1000.0
        assert result.cash_balance == 9000.0
        assert result.position_quantity == 10

        portfolio = get_portfolio(engine, cache)
        assert portfolio["cash_balance"] == 9000.0
        assert portfolio["positions"][0]["avg_cost"] == 100.0
        assert portfolio["total_value"] == 10000.0

    def test_second_buy_averages_cost(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 10)
        cache.update("AAPL", 200.0)
        execute_trade(engine, cache, "AAPL", "buy", 10)

        position = get_portfolio(engine, cache)["positions"][0]
        assert position["quantity"] == 20
        assert position["avg_cost"] == 150.0
        assert position["unrealized_pnl"] == 1000.0

    def test_fractional_shares(self, engine, cache):
        result = execute_trade(engine, cache, "AAPL", "buy", 0.5)
        assert result.cash_balance == 9950.0

    def test_insufficient_cash_rejected_and_nothing_written(self, engine, cache):
        with pytest.raises(TradeError, match="Insufficient cash"):
            execute_trade(engine, cache, "AAPL", "buy", 101)

        assert _count(engine, trades) == 0
        assert _count(engine, positions) == 0
        assert get_portfolio(engine, cache)["cash_balance"] == 10000.0

    def test_exact_cash_allowed(self, engine, cache):
        result = execute_trade(engine, cache, "AAPL", "buy", 100)
        assert result.cash_balance == 0.0


class TestSell:
    def test_partial_sell_keeps_avg_cost(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 10)
        cache.update("AAPL", 120.0)
        result = execute_trade(engine, cache, "AAPL", "sell", 4)

        assert result.cash_balance == 9480.0
        position = get_portfolio(engine, cache)["positions"][0]
        assert position["quantity"] == 6
        assert position["avg_cost"] == 100.0

    def test_sell_all_deletes_position(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 10)
        result = execute_trade(engine, cache, "AAPL", "sell", 10)

        assert result.position_quantity == 0
        assert _count(engine, positions) == 0

    def test_sell_at_a_loss(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 10)
        cache.update("AAPL", 80.0)
        result = execute_trade(engine, cache, "AAPL", "sell", 10)

        assert result.cash_balance == 9800.0

    def test_selling_more_than_held_rejected(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 5)
        with pytest.raises(TradeError, match="you hold 5"):
            execute_trade(engine, cache, "AAPL", "sell", 6)

    def test_selling_unheld_rejected(self, engine, cache):
        with pytest.raises(TradeError, match="you hold 0"):
            execute_trade(engine, cache, "MSFT", "sell", 1)


class TestValidation:
    @pytest.mark.parametrize("qty", [0, -1, float("nan"), float("inf"), 1e-9])
    def test_bad_quantity(self, engine, cache, qty):
        with pytest.raises(TradeError):
            execute_trade(engine, cache, "AAPL", "buy", qty)

    def test_bad_side(self, engine, cache):
        with pytest.raises(TradeError, match="Side"):
            execute_trade(engine, cache, "AAPL", "hold", 1)

    def test_no_price(self, engine, cache):
        with pytest.raises(TradeError, match="No live price for TSLA"):
            execute_trade(engine, cache, "TSLA", "buy", 1)

    @pytest.mark.parametrize("raw", ["", "1ABC", "TOOLONGTICKER", "A B", "$$"])
    def test_bad_ticker(self, raw):
        with pytest.raises(InvalidTickerError):
            normalize_ticker(raw)

    @pytest.mark.parametrize("raw,expected", [(" aapl ", "AAPL"), ("brk.b", "BRK.B")])
    def test_ticker_normalised(self, raw, expected):
        assert normalize_ticker(raw) == expected


class TestValuationAndSnapshots:
    def test_trade_records_snapshot(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 10)
        assert _count(engine, portfolio_snapshots) == 1

    def test_unpriced_position_valued_at_cost(self, engine, cache):
        execute_trade(engine, cache, "AAPL", "buy", 10)
        cache.remove("AAPL")

        position = get_portfolio(engine, cache)["positions"][0]
        assert position["price_available"] is False
        assert position["current_price"] == 100.0
        assert position["unrealized_pnl"] == 0.0

    def test_history_oldest_first(self, engine, cache):
        record_snapshot(engine, cache)
        execute_trade(engine, cache, "AAPL", "buy", 10)
        cache.update("AAPL", 110.0)
        record_snapshot(engine, cache)

        values = [s["total_value"] for s in get_history(engine)]
        assert values == [10000.0, 10000.0, 10100.0]

    def test_cash_never_drifts(self, engine, cache):
        cache.update("AAPL", 33.33)
        for _ in range(30):
            execute_trade(engine, cache, "AAPL", "buy", 1)
        for _ in range(30):
            execute_trade(engine, cache, "AAPL", "sell", 1)

        assert get_portfolio(engine, cache)["cash_balance"] == 10000.0
        assert _count(engine, positions) == 0
