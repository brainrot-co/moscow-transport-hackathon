FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --group worker --no-install-project

# веса Chronos запечены в образ (~0.5 ГБ): первый пересчёт не ждёт скачивания и не зависит
# от сети и лимитов Hugging Face; на RAM это не влияет;
# слой выше кода, чтобы правки кода не скачивали веса заново
ENV PATH=/app/.venv/bin:$PATH DATA_DIR=/data HF_HOME=/opt/hf
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('amazon/chronos-2')"
ENV HF_HUB_OFFLINE=1

COPY ml/src ml/src

# Справочники пока зашиты в образ
# TODO: вынести в отдельный том, чтобы не пересобирать образ при их обновлении
COPY dataset/external/calendar.csv dataset/external/school_holidays_moscow.csv \
    dataset/external/correction_factors.json dataset/external/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --group worker

CMD ["python", "-m", "mtml.worker", "run"]
