FROM python:3.12-slim

# Pinned: a mutable tag lets an upstream uv release change resolver behaviour
# between two builds of the same commit.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so the layer caches across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

# The elder and family pages. Easy to forget, and their absence shows up only
# as a 404 on the deployed service — the API keeps working perfectly.
COPY static ./static

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Cloud Run supplies PORT. One worker: WebSocket sessions are stateful and
# session affinity across instances is best-effort only.
CMD exec uvicorn sampan.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
