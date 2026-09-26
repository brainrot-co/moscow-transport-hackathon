FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY ml/src ml/src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

ENV PATH=/app/.venv/bin:$PATH DATA_DIR=/data
CMD ["python", "-m", "mtml.ingest", "run"]
