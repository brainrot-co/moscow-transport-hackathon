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

    # вчерашний день маршрута становится final досрочно, если набрал эту долю ожидаемого объёма
    # (медиана того же дня недели за 4 недели). Порог низкий намеренно: недогрузку к D+1 (≈ −2.6%)
    # по объёму не отличить от тихого дня (разброс ±10–20%), ловится только грубая дыра вроде
    # невыгрузившегося парка; у 95% полных дней объём выше 0.8
    completeness_ratio: float = 0.8

    # день маршрута с объёмом ниже этой доли ожидаемого помечается anomaly (ремонт, отмена, сбой);
    # флаг для лога и интерфейса, статус он не понижает
    anomaly_ratio: float = 0.5

    # валидации раньше этой даты — битые даты (вроде 1970-01-01), строки уходят в карантин
    min_date: date = date(2020, 1, 1)

    # маршруты из справочника; валидации других маршрутов принимаются, но считаются отдельно
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
