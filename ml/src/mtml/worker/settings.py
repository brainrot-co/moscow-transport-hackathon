import os
from dataclasses import dataclass
from datetime import time

from mtml.data import ALL_ROUTES


@dataclass(frozen=True)
class WorkerSettings:
    # Актуальная модель
    model: str = "ensemble_cal_school_daytype_profile"

    # на этом горизонте модель проверена бэктестами, дальше отвечает годовой прогон
    horizon_days: int = 61

    # годовой прогон: сезонная модель на год вперёд от водяного знака
    year_days: int = 365

    # сколько последних прогонов хранить в state/runs
    keep_runs: int = 14

    # маршруты, на которые строится прогноз; маршрут без истории получает 0 (cold start)
    routes: tuple[int, ...] = ALL_ROUTES

    # как часто цикл проверяет водяной знак и расписание, реальные секунды
    poll_sec: int = 60

    # любой пересчёт (сдвиг водяного знака, ночь) не чаще, реальные минуты: при ускоренных
    # часах демо оба наступают каждые секунды, а прогон занимает ~20 секунд
    min_rerun_minutes: int = 10

    # ночной прогон по часам системы, даже если водяной знак не сдвинулся
    run_at: time = time(3, 0)

    @classmethod
    def from_env(cls):
        env = os.environ
        routes = env.get("ROUTES")
        return cls(
            model=env.get("ML_MODEL", cls.model),
            horizon_days=int(env.get("SHORT_HORIZON_DAYS", cls.horizon_days)),
            year_days=int(env.get("YEAR_HORIZON_DAYS", cls.year_days)),
            keep_runs=int(env.get("KEEP_RUNS", cls.keep_runs)),
            routes=tuple(int(r) for r in routes.split(",")) if routes else cls.routes,
            poll_sec=int(env.get("WORKER_POLL_SEC", cls.poll_sec)),
            min_rerun_minutes=int(env.get("MIN_RERUN_MINUTES", cls.min_rerun_minutes)),
            run_at=time.fromisoformat(env.get("SHORT_RUN_AT", cls.run_at.isoformat())),
        )
