FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so the layer caches across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Cloud Run supplies PORT. One worker: WebSocket sessions are stateful and
# session affinity across instances is best-effort only.
CMD exec uvicorn sampan.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
