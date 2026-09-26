from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core import get_settings
from app.db import DatabaseClient, RedisClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    app.state.db = DatabaseClient(
        url=settings.database_url,
    )

    app.state.redis = RedisClient(
        url=settings.redis_url,
    )

    yield

    await app.state.db.dispose()
    await app.state.redis.close()
