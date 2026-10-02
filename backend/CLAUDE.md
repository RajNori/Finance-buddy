# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
```

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `timestamp`, `session_open`, plus properties `change`, `change_percent`, `session_change_percent`, `direction` ("up"/"down"/"flat"), and `to_dict()` for JSON serialization.

- **`PriceCache`** — Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None) -> PriceUpdate`
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `remove(ticker)`
  - `version` property — monotonic counter, increments on every update (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
```

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Application Layout

```
app/
├── main.py          # create_app() factory: lifespan wires DB, market source, snapshot loop
├── db/              # SQLAlchemy Core schema, engine (DATABASE_URL), init/seed
├── services/        # Sync business logic, no HTTP: portfolio, watchlist, tracking
├── api/             # Routes + {"error": ...} handlers; DB calls via run_in_threadpool
└── market/          # Price cache, simulator, Massive client, SSE stream
```

- **State** lives on `app.state`: `engine`, `price_cache`, `market_source`.
- **Price tracking** = watchlist ∪ held positions. After any watchlist change or closed position, call `services.tracking.sync_ticker`.
- **Portability:** SQL must work on SQLite and Postgres. Use SQLAlchemy Core; no raw SQL or dialect-specific types.
- **Tests:** use the `engine`, `db_url` and `client` fixtures in `tests/conftest.py`.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint

# Same DB/API suites against Postgres (CI does this on every PR)
TEST_POSTGRES_URL=postgresql+psycopg://user:pass@localhost:5432/test \
  uv run --extra dev pytest tests/test_db.py tests/test_portfolio.py tests/test_api.py
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
