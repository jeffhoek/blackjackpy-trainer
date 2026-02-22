FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer unless lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY blackjack/ blackjack/
COPY web/ web/
COPY data/ data/

# Cloud Run injects PORT (default 8080); shell form needed for $PORT expansion
CMD ["/bin/sh", "-c", ".venv/bin/uvicorn web.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
