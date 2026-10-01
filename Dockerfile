# syntax=docker/dockerfile:1.7
#
# Multi-stage build: Node builds the static frontend export, Python serves it
# alongside the API on a single port. Built for linux/amd64 in CI (ECS Fargate).

# ---- Stage 1: frontend static export ----------------------------------------
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/ ./
# Until the Next.js app exists, emit a placeholder page so the image still builds.
RUN if [ -f package.json ]; then \
      npm ci && npm run build; \
    else \
      mkdir -p out && \
      printf '<!doctype html><title>Financebuddy</title><p>Frontend not built yet.</p>\n' > out/index.html; \
    fi

# ---- Stage 2: Python runtime -------------------------------------------------
FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first for layer caching.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY --from=frontend /frontend/out ./static

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/db \
    && chown -R app:app /app/db
USER app

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 20"]
