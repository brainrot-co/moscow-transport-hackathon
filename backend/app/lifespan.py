import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import get_settings
from app.core.security import hash_password
from app.db import DatabaseClient, RedisClient
from app.enums import Role
from app.ml import ForecastStore
from app.models import User


async def _reload_forecast_store(store: ForecastStore, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        await store.load()


async def _ensure_demo_user(app: FastAPI) -> None:
    settings = get_settings()
    if not settings.demo_username or not settings.demo_password:
        return
    async with app.state.db.session_factory() as session:
        existing = await session.scalar(
            select(User).where(User.username == settings.demo_username.lower())
        )
        if existing is None:
            session.add(
                User(
                    username=settings.demo_username.lower(),
                    email=settings.demo_email,
                    password_hash=hash_password(settings.demo_password),
                    role=Role.ADMIN,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                # воркеры uvicorn стартуют одновременно: пользователя создал соседний
                await session.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    app.state.db = DatabaseClient(
        url=settings.database_url,
    )

    app.state.redis = RedisClient(
        url=settings.redis_url,
    )
    await _ensure_demo_user(app)
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
