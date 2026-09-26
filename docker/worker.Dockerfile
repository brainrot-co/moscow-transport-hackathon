FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --group worker --no-install-project

COPY ml/src ml/src

# Справочники пока зашиты в образ
# TODO: вынести в отдельный том, чтобы не пересобирать образ при их обновлении
COPY dataset/external/calendar.csv dataset/external/school_holidays_moscow.csv dataset/external/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --group worker

# веса Chronos скачиваются при первом запуске и кэшируются на общем томе
ENV PATH=/app/.venv/bin:$PATH DATA_DIR=/data HF_HOME=/data/hf
CMD ["python", "-m", "mtml.worker", "run"]
