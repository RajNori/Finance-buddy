"""FastAPI application entrypoint.

Wires the database, market data, background snapshots, REST API, SSE stream
and the static frontend export into a single ASGI app on one port.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.api.errors import register_error_handlers
from app.api.routes import router as api_router
from app.db import init_db, make_engine
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.services.portfolio import record_snapshot
from app.services.tracking import tracked_tickers

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parent.parent / "static"))
SNAPSHOT_INTERVAL_SECONDS = float(os.environ.get("SNAPSHOT_INTERVAL_SECONDS", "60"))


async def _snapshot_loop(app: FastAPI, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await run_in_threadpool(record_snapshot, app.state.engine, app.state.price_cache)
        except Exception:
            logger.exception("Portfolio snapshot failed")


def create_app(
    database_url: str | None = None,
    snapshot_interval: float = SNAPSHOT_INTERVAL_SECONDS,
) -> FastAPI:
    price_cache = PriceCache()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(database_url)
        await run_in_threadpool(init_db, engine)
        tickers = await run_in_threadpool(tracked_tickers, engine)

        source = create_market_data_source(price_cache)
        await source.start(tickers)

        app.state.engine = engine
        app.state.price_cache = price_cache
        app.state.market_source = source

        snapshots = asyncio.create_task(
            _snapshot_loop(app, snapshot_interval), name="portfolio-snapshots"
        )
        logger.info(
            "Financebuddy started (version=%s, db=%s, tickers=%d)",
            os.environ.get("APP_VERSION", "dev"),
            engine.url.get_backend_name(),
            len(tickers),
        )
        try:
            yield
        finally:
            snapshots.cancel()
            with suppress(asyncio.CancelledError):
                await snapshots
            await source.stop()
            engine.dispose()

    app = FastAPI(title="Financebuddy", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(api_router)
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

    return app


app = create_app()
