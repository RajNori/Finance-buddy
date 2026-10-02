"""Tests for the FastAPI entrypoint."""


def test_health_returns_ok_and_seeds_prices(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["tickers"] == 10
