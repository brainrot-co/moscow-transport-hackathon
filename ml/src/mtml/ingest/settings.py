import os
from dataclasses import dataclass
from datetime import date

from mtml.data import ALL_ROUTES


@dataclass(frozen=True)
class IngestSettings:
    # Частота опроса папки inbox на предмет новых файлов, сек
    poll_sec: int = 60

    # Данные за день считаются финализированными, если день старше этого числа дней относительно now
    finalize_after_days: int = 3

    # доля маршрутов, которые должны быть в дне, чтобы день считался полным
    completeness_ratio: float = 0.97

    # доля аномалий, при которой день считается аномальным
    anomaly_ratio: float = 0.5

    # минимальная дата, с которой загружается история, отсеиваем очень старые файлы
    min_date: date = date(2020, 1, 1)

    # маршруты, которые загружаются; пустой кортеж = все маршруты
    routes: tuple[int, ...] = ALL_ROUTES

    # ограничение памяти для DuckDB; если данных больше, чем это, DuckDB сбрасывает их в spill
    memory_limit: str = "1GB"

    @classmethod
    def from_env(cls):
        env = os.environ
        routes = env.get("ROUTES")
        return cls(
            poll_sec=int(env.get("INGEST_POLL_SEC", cls.poll_sec)),
            finalize_after_days=int(env.get("FINALIZE_AFTER_DAYS", cls.finalize_after_days)),
            completeness_ratio=float(env.get("COMPLETENESS_RATIO", cls.completeness_ratio)),
            anomaly_ratio=float(env.get("ANOMALY_RATIO", cls.anomaly_ratio)),
            min_date=date.fromisoformat(env.get("MIN_DATE", cls.min_date.isoformat())),
            routes=tuple(int(r) for r in routes.split(",")) if routes else cls.routes,
            memory_limit=env.get("INGEST_MEMORY_LIMIT", cls.memory_limit),
        )
