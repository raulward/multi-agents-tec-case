FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml ./

RUN uv sync --no-dev --group ui --no-install-project \
    && rm -rf /root/.cache/uv

COPY . .

RUN chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000 8501