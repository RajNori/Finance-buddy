"""FastAPI application entrypoint.

Wires the market data subsystem, the SSE stream, a health check and the
static frontend export into a single ASGI app served on one port.

Portfolio, watchlist, chat and database routes are added by later work.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.market import PriceCache, create_market_data_source, create_stream_router
from app.market.seed_prices import SEED_PRICES

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parent.parent / "static"))
DEFAULT_TICKERS = list(SEED_PRICES.keys())

price_cache = PriceCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = create_market_data_source(price_cache)
    await source.start(DEFAULT_TICKERS)
    app.state.market_source = source
    logger.info("Financebuddy started (version=%s)", os.environ.get("APP_VERSION", "dev"))
    try:
        yield
    finally:
        await source.stop()


app = FastAPI(title="Financebuddy", lifespan=lifespan)
app.include_router(create_stream_router(price_cache))


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, str | int]:
    """Liveness check for the load balancer. Must stay cheap and dependency-free."""
    return {
        "status": "ok",
        "version": os.environ.get("APP_VERSION", "dev"),
        "tickers": len(price_cache),
    }


# Static frontend last, so /api/* routes take precedence.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    logger.warning("Static directory %s not found; serving API only", STATIC_DIR)
