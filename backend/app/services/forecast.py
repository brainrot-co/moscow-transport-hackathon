from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.ml.aggregation import Granularity, aggregate_rows
from app.ml.corrections import Scenario, apply_corrections
from app.ml.load import (
    DayKind,
    LoadLevel,
    LoadNorm,
    LoadNormSettings,
    day_kind,
    route_norm,
)
from app.ml.models import ForecastSnapshot, ResponseRow


@dataclass(frozen=True, slots=True)
class RouteLoad:
    route: int
    value: float | None
    level: LoadLevel | None
    norm: LoadNorm | None


class ForecastService:
    def __init__(self, snapshot: ForecastSnapshot | None):
        self.snapshot = snapshot

    def meta(
        self,
        error: str | None = None,
        *,
        now: datetime | None = None,
        published_at: datetime | None = None,
        stale_after_days: int = 3,
    ) -> dict[str, object]:
        snapshot = self.snapshot
        if snapshot is None:
            return {"available": False, "error": error or "forecast is unavailable"}
        return {
            "available": True,
            "short_run_id": snapshot.short_meta.run_id if snapshot.short_meta else None,
            "year_run_id": snapshot.year_meta.run_id if snapshot.year_meta else None,
            "watermark": snapshot.watermark,
            "data_cutoff": (
                snapshot.short_meta.data_cutoff if snapshot.short_meta else None
            ),
            "now": now,
            "published_at": published_at,
            "stale": bool(
                now
                and snapshot.watermark
                and (now.date() - snapshot.watermark).days > stale_after_days
            ),
            "cold_start_routes": sorted(
                (snapshot.short_meta.cold_start_routes if snapshot.short_meta else set())
                | (snapshot.year_meta.cold_start_routes if snapshot.year_meta else set())
            ),
            "model": {
                "short": snapshot.short_meta.model_name if snapshot.short_meta else None,
                "year": snapshot.year_meta.model_name if snapshot.year_meta else None,
            },
        }

    def hourly(
        self,
        date_from: datetime,
        date_to: datetime,
        routes: list[int] | None = None,
        model_factors: dict[str, float] | None = None,
        scenarios: list[Scenario] | None = None,
        granularity: Granularity = "hour",
        now: datetime | None = None,
    ) -> list[ResponseRow]:
        if self.snapshot is None:
            return []
        available_routes = {
            route
            for route, _ in (
                set(self.snapshot.actuals)
                | set(self.snapshot.short)
                | set(self.snapshot.year)
            )
        }
        selected_routes = set(routes) if routes else available_routes
        result: list[ResponseRow] = []
        timestamp = _moscow_naive(date_from)
        date_to = _moscow_naive(date_to)
        while timestamp <= date_to:
            for route in sorted(selected_routes):
                result.append(self.snapshot.resolve(route, timestamp, now))
            timestamp += timedelta(hours=1)
        corrected = apply_corrections(
            result,
            self.snapshot.effects,
            model_factors=model_factors,
            scenarios=scenarios,
        )
        return aggregate_rows(corrected, granularity)

    def day_kind(self, day: date) -> DayKind:
        return day_kind(day, self.snapshot.day_types if self.snapshot else {})

    def route_loads(
        self,
        day: date,
        routes: list[int] | None,
        settings: LoadNormSettings,
        model_factors: dict[str, float] | None = None,
        scenarios: list[Scenario] | None = None,
        now: datetime | None = None,
    ) -> list[RouteLoad]:
        snapshot = self.snapshot
        if snapshot is None:
            return []
        rows = self.hourly(
            datetime.combine(day, time()),
            datetime.combine(day, time(23)),
            routes,
            model_factors=model_factors,
            scenarios=scenarios,
            granularity="day",
            now=now,
        )
        return self.route_loads_from_rows(day, rows, settings)

    def route_loads_from_rows(
        self,
        day: date,
        rows: list[ResponseRow],
        settings: LoadNormSettings,
    ) -> list[RouteLoad]:
        """rows — по одной дневной строке на маршрут (granularity="day")."""
        result: list[RouteLoad] = []
        for row in rows:
            value = (
                (row.value or 0) + (row.yhat or 0) if row.source is not None else None
            )
            result.append(self.route_load(day, row.route, value, settings))
        return result

    def route_load(
        self,
        day: date,
        route: int,
        value: float | None,
        settings: LoadNormSettings,
    ) -> RouteLoad:
        """Уровень загрузки по сумме посадок маршрута за день."""
        norm = self._route_norm(route, self.day_kind(day), settings)
        level = norm.level(value) if norm is not None and value is not None else None
        return RouteLoad(route, value, level, norm)

    def _route_norm(
        self, route: int, kind: DayKind, settings: LoadNormSettings
    ) -> LoadNorm | None:
        snapshot = self.snapshot
        if snapshot is None or snapshot.watermark is None:
            return None
        # норма зависит только от снапшота и настроек: считаем один раз на снапшот
        cache_key = (
            route,
            kind,
            snapshot.watermark,
            settings.weeks,
            settings.min_days,
            settings.low_quantile,
            settings.high_quantile,
            settings.min_deviation,
        )
        if cache_key not in snapshot.norm_cache:
            snapshot.norm_cache[cache_key] = route_norm(
                snapshot.daily_actuals.get(route, {}),
                kind,
                snapshot.day_types,
                snapshot.watermark,
                settings,
            )
        return snapshot.norm_cache[cache_key]  # type: ignore[return-value]


def as_api_rows(rows: list[ResponseRow]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    timezone = ZoneInfo("Europe/Moscow")
    for row in rows:
        data = row.as_dict()
        data["ts"] = row.ts.replace(tzinfo=timezone).isoformat()
        result.append(data)
    return result


def _moscow_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(minute=0, second=0, microsecond=0)
    return value.astimezone(ZoneInfo("Europe/Moscow")).replace(
        tzinfo=None, minute=0, second=0, microsecond=0
    )
