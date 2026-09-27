import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.logger import logger

# растёт при каждом изменении поправок; входит в ключи кэша прогноза, поэтому
# после сохранения поправки все воркеры сразу перестают отдавать старые ответы
SCENARIOS_VERSION_KEY = "forecast:scenarios_version"


async def current_version(client: redis.Redis) -> int | None:
    """None, если Redis недоступен: тогда кэш прогноза не используется."""
    try:
        value = await client.get(SCENARIOS_VERSION_KEY)
    except RedisError as error:
        logger.warning("версия поправок не прочитана из Redis: %s", error)
        return None
    return int(value) if value is not None else 0


async def bump_version(client: redis.Redis) -> None:
    try:
        await client.incr(SCENARIOS_VERSION_KEY)
    except RedisError as error:
        logger.warning("версия поправок не обновлена в Redis: %s", error)
