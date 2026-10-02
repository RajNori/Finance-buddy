"""Uniform error contract: every API error is {"error": "<message>"}."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.portfolio import InvalidTickerError, TradeError
from app.services.watchlist import TickerNotFoundError


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TradeError)
    async def _trade(_: Request, exc: TradeError) -> JSONResponse:
        return _error(400, str(exc))

    @app.exception_handler(InvalidTickerError)
    async def _ticker(_: Request, exc: InvalidTickerError) -> JSONResponse:
        return _error(400, str(exc))

    @app.exception_handler(TickerNotFoundError)
    async def _not_found(_: Request, exc: TickerNotFoundError) -> JSONResponse:
        return _error(404, str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        message = first.get("msg", "Invalid request")
        return _error(400, f"{field}: {message}" if field else message)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))
