import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://demo:demo@127.0.0.1:5432/demo"
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("ACCESS_SECRET", "local-demo-access-secret-32-characters")
os.environ.setdefault("REFRESH_SECRET", "local-demo-refresh-secret-32-characters")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")
os.environ.setdefault(
    "CORS_ORIGINS",
    '["http://127.0.0.1:5173", "http://localhost:5173"]',
)

from app.core import hash_password
from app.dependencies.crud import get_user_crud
from app.dependencies.database import get_db_session
from app.dependencies.redis import get_redis_client
from app.dependencies.scenario import get_scenario_crud
from app.enums import Role
from app.main import app
from app.ml import ForecastStore
from app.ml.models import ActualRecord, ForecastRecord, ForecastSnapshot, RunMetadata
from app.models import User

HOURLY_DEMAND = (
    0.18,
    0.14,
    0.11,
    0.1,
    0.14,
    0.32,
    0.72,
    1.18,
    1.42,
    1.12,
    0.86,
    0.78,
    0.82,
    0.88,
    0.92,
    1.02,
    1.28,
    1.55,
    1.48,
    1.2,
    0.92,
    0.68,
    0.46,
    0.28,
)


class InMemoryRedis:
    def __init__(self):
        self.values: dict[str, object] = {}

    async def setex(self, key: str, _ttl: int, value: object) -> bool:
        self.values[key] = value
        return True

    async def getdel(self, key: str):
        return self.values.pop(key, None)


class HealthyService:
    async def ping(self) -> bool:
        return True


class HealthyRedisService(HealthyService):
    def __init__(self, client: InMemoryRedis):
        self.client = client

    def get_client(self) -> InMemoryRedis:
        return self.client


class InMemoryUserCRUD:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.users = {
            1: User(
                id=1,
                username="demo",
                email="demo@transport.local",
                password_hash=hash_password("demo-transport"),
                is_active=True,
                role=Role.ADMIN,
                created_at=now,
                updated_at=now,
            )
        }
        self.next_id = 2

    async def create_user(self, _session, user):
        now = datetime.now(timezone.utc)
        user.id = self.next_id
        self.next_id += 1
        user.is_active = True
        user.role = Role.USER
        user.created_at = now
        user.updated_at = now
        self.users[user.id] = user
        return user

    async def get_by_id(self, _session, user_id: int):
        return self.users.get(user_id)

    async def get_by_username(self, _session, username: str):
        return next(
            (user for user in self.users.values() if user.username == username), None
        )

    async def get_all_users(self, _session):
        return list(self.users.values())


class InMemoryScenarioCRUD:
    def __init__(self):
        self.items = []
        self.next_id = 1

    async def list(self, _session, active=None, date_from=None, date_to=None):
        items = self.items
        if active is not None:
            items = [item for item in items if item.active == active]
        if date_from is not None:
            items = [item for item in items if item.date_to >= date_from]
        if date_to is not None:
            items = [item for item in items if item.date_from <= date_to]
        return sorted(items, key=lambda item: (item.date_from, item.id))

    async def get(self, _session, scenario_id: int):
        return next((item for item in self.items if item.id == scenario_id), None)

    async def create(self, _session, scenario):
        now = datetime.now(timezone.utc)
        scenario.id = self.next_id
        self.next_id += 1
        scenario.created_at = now
        scenario.updated_at = now
        self.items.append(scenario)
        return scenario

    async def delete(self, _session, scenario) -> None:
        self.items.remove(scenario)


redis_client = InMemoryRedis()
user_crud = InMemoryUserCRUD()
scenario_crud = InMemoryScenarioCRUD()


async def memory_session():
    yield None


def build_demo_snapshot(now: datetime):
    route_loads = {
        1: 71,
        5: 48,
        7: 58,
        11: 64,
        12: 73,
        17: 82,
        25: 61,
        26: 42,
        28: 52,
        50: 69,
    }
    routes = frozenset(route_loads)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    actuals = {}
    forecasts = {}
    daily_actuals = {}
    for hour in range(24):
        timestamp = start.replace(hour=hour)
        for route in routes:
            base = round(route_loads[route] * HOURLY_DEMAND[hour])
            if hour <= now.hour:
                actuals[(route, timestamp)] = ActualRecord(route, timestamp, base)
            else:
                forecasts[(route, timestamp)] = ForecastRecord(
                    route,
                    timestamp,
                    float(round(base * 1.05)),
                    float(round(base * 0.9)),
                    float(round(base * 1.18)),
                )
    for route, route_load in route_loads.items():
        usual_total = sum(round(route_load * factor) for factor in HOURLY_DEMAND)
        route_factor = 0.85 + (route % 5) * 0.04
        daily_actuals[route] = {
            now.date() - timedelta(days=offset): round(
                usual_total
                * route_factor
                * (0.78 if (now - timedelta(days=offset)).weekday() >= 5 else 1)
                * (0.96 + (offset % 5) * 0.02)
            )
            for offset in range(1, 64)
        }
    meta = RunMetadata(
        run_id="local-demo",
        kind="short",
        schema_version=1,
        data_cutoff=now.date(),
        step="hour",
        routes=routes,
        model_name="local-demo",
    )
    return ForecastSnapshot(
        actuals=actuals,
        short=forecasts,
        year={},
        short_meta=meta,
        watermark=now.date(),
        daily_actuals=daily_actuals,
    )


@asynccontextmanager
async def standalone_lifespan(current_app):
    now = datetime.now(ZoneInfo("Europe/Moscow")).replace(tzinfo=None)
    current_app.state.db = HealthyService()
    current_app.state.redis = HealthyRedisService(redis_client)
    store = ForecastStore("/tmp/unused")
    await store.replace(build_demo_snapshot(now))
    store._active = {"published_at": now.isoformat()}
    current_app.state.forecast_store = store
    yield


app.dependency_overrides[get_db_session] = memory_session
app.dependency_overrides[get_redis_client] = lambda: redis_client
app.dependency_overrides[get_user_crud] = lambda: user_crud
app.dependency_overrides[get_scenario_crud] = lambda: scenario_crud
app.router.lifespan_context = standalone_lifespan
