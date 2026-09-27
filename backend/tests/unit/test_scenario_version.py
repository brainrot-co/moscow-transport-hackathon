from fakeredis.aioredis import FakeRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.scenario_version import bump_version, current_version


async def test_version_starts_at_zero_and_grows_on_bump():
    client = FakeRedis()

    assert await current_version(client) == 0
    await bump_version(client)
    await bump_version(client)
    assert await current_version(client) == 2


class BrokenRedis:
    async def get(self, _key):
        raise RedisConnectionError("down")

    async def incr(self, _key):
        raise RedisConnectionError("down")


async def test_unavailable_redis_turns_cache_off_without_errors():
    client = BrokenRedis()

    assert await current_version(client) is None
    await bump_version(client)
