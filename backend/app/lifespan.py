import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core import get_settings
from app.db import DatabaseClient, RedisClient
from app.ml import ForecastStore


async def _reload_forecast_store(store: ForecastStore, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        await store.load()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    app.state.db = DatabaseClient(
        url=settings.database_url,
    )

    app.state.redis = RedisClient(
        url=settings.redis_url,
    )
    app.state.forecast_store = ForecastStore(settings.data_dir)
    await app.state.forecast_store.load()
    reload_task = asyncio.create_task(
        _reload_forecast_store(
            app.state.forecast_store,
            settings.backend_reload_sec,
        )
    )

    try:
        yield
    finally:
        reload_task.cancel()
        await asyncio.gather(reload_task, return_exceptions=True)

        await app.state.db.dispose()
        await app.state.redis.close()
