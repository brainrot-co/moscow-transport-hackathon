import os
from dataclasses import dataclass

from mtml.data import ALL_ROUTES


@dataclass(frozen=True)
class WorkerSettings:
    # Актуальная модель
    model: str = "chronos2_daily_cal_school_daytype"

    # на этом горизонте модель проверена бэктестами, дальше отвечает годовой прогон
    horizon_days: int = 61

    # сколько последних прогонов хранить в state/runs
    keep_runs: int = 14

    # маршруты, которые загружаются; пустой кортеж = все маршруты
    routes: tuple[int, ...] = ALL_ROUTES

    @classmethod
    def from_env(cls):
        env = os.environ
        routes = env.get("ROUTES")
        return cls(
            model=env.get("ML_MODEL", cls.model),
            horizon_days=int(env.get("SHORT_HORIZON_DAYS", cls.horizon_days)),
            keep_runs=int(env.get("KEEP_RUNS", cls.keep_runs)),
            routes=tuple(int(r) for r in routes.split(",")) if routes else cls.routes,
        )
