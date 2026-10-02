"""HTTP contract for portfolio and watchlist endpoints (PLAN.md §8)."""


def _price(client, ticker):
    items = client.get("/api/watchlist").json()["tickers"]
    return next(i["price"] for i in items if i["ticker"] == ticker)


class TestPortfolioApi:
    def test_fresh_portfolio(self, client):
        body = client.get("/api/portfolio").json()

        assert body["cash_balance"] == 10000.0
        assert body["positions"] == []
        assert body["total_value"] == 10000.0

    def test_buy_then_sell(self, client):
        buy = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 2, "side": "buy"})
        assert buy.status_code == 200
        trade = buy.json()["trade"]
        assert trade["cash_balance"] == round(10000 - trade["total"], 2)

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["positions"][0]["ticker"] == "AAPL"
        assert portfolio["positions"][0]["quantity"] == 2

        sell = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 2, "side": "sell"})
        assert sell.status_code == 200
        assert client.get("/api/portfolio").json()["positions"] == []

    def test_insufficient_cash_is_400_with_error(self, client):
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1_000_000, "side": "buy"}
        )
        assert response.status_code == 400
        assert "Insufficient cash" in response.json()["error"]

    def test_invalid_side_is_400_with_error(self, client):
        response = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "short"})
        assert response.status_code == 400
        assert "side" in response.json()["error"]

    def test_unwatched_ticker_is_400(self, client):
        response = client.post("/api/portfolio/trade", json={"ticker": "PYPL", "quantity": 1, "side": "buy"})
        assert response.status_code == 400
        assert "Add it to the watchlist" in response.json()["error"]

    def test_history_has_snapshot_after_trade(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 1, "side": "buy"})
        snapshots = client.get("/api/portfolio/history").json()["snapshots"]
        assert len(snapshots) == 1
        assert set(snapshots[0]) == {"total_value", "recorded_at"}


class TestWatchlistApi:
    def test_default_watchlist_has_prices(self, client):
        items = client.get("/api/watchlist").json()["tickers"]

        assert len(items) == 10
        assert all(i["price"] > 0 for i in items)
        assert "session_change_percent" in items[0]

    def test_add_prices_immediately_and_is_idempotent(self, client):
        first = client.post("/api/watchlist", json={"ticker": "pypl"})
        assert first.json() == {"ticker": "PYPL", "added": True}
        assert _price(client, "PYPL") > 0

        again = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert again.json()["added"] is False

    def test_add_invalid_ticker_is_400(self, client):
        response = client.post("/api/watchlist", json={"ticker": "not a ticker"})
        assert response.status_code == 400
        assert "Invalid ticker" in response.json()["error"]

    def test_remove(self, client):
        assert client.delete("/api/watchlist/NFLX").status_code == 200
        tickers = [i["ticker"] for i in client.get("/api/watchlist").json()["tickers"]]
        assert "NFLX" not in tickers

    def test_remove_missing_is_404(self, client):
        response = client.delete("/api/watchlist/PYPL")
        assert response.status_code == 404
        assert response.json() == {"error": "PYPL is not on the watchlist"}

    def test_removed_ticker_with_position_keeps_pricing(self, client):
        client.post("/api/portfolio/trade", json={"ticker": "TSLA", "quantity": 1, "side": "buy"})
        client.delete("/api/watchlist/TSLA")

        position = client.get("/api/portfolio").json()["positions"][0]
        assert position["ticker"] == "TSLA"
        assert position["price_available"] is True

        # Closing it now stops pricing, since it's neither watched nor held.
        client.post("/api/portfolio/trade", json={"ticker": "TSLA", "quantity": 1, "side": "sell"})
        source = client.app.state.market_source
        assert "TSLA" not in source.get_tickers()

    def test_unknown_route_uses_error_shape(self, client):
        response = client.get("/api/nope")
        assert response.status_code == 404
        assert "error" in response.json()
