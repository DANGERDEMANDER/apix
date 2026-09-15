FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.4.27 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml /app/
COPY backend /app/backend
COPY config /app/config

RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend

EXPOSE 8000
CMD ["uvicorn", "apix.main:app", "--host", "0.0.0.0", "--port", "8000"]