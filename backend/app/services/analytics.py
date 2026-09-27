from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time

from app.ml.corrections import Scenario
from app.ml.load import LoadLevel, LoadNormSettings
from app.ml.models import ResponseRow, Source
from app.services.forecast import ForecastService, RouteLoad


@dataclass(frozen=True, slots=True)
class AnalyticsHour:
    ts: datetime
    actual: float | None
    forecast: float | None
    total: float | None
    available_routes: int
    total_routes: int


@dataclass(frozen=True, slots=True)
class AnalyticsRoute:
    route: int
    hourly: tuple[float | None, ...]
    hourly_sources: tuple[Source | None, ...]
    actual: float
    forecast: float
    total: float | None
    peak_hour: int | None
    peak_value: float | None
    ratio: float | None
    deviation_percent: float | None
    load_level: LoadLevel | None
    norm_median: float | None
    norm_days: int


@dataclass(frozen=True, slots=True)
class ForecastAnalytics:
    day: date
    selected_routes: tuple[int, ...]
    hours: tuple[AnalyticsHour, ...]
    routes: tuple[AnalyticsRoute, ...]


def build_forecast_analytics(
    service: ForecastService,
    day: date,
    routes: list[int] | None,
    settings: LoadNormSettings,
    model_factors: dict[str, float] | None = None,
    scenarios: list[Scenario] | None = None,
):
    rows = service.hourly(
        datetime.combine(day, time()),
        datetime.combine(day, time(23)),
        routes,
        model_factors=model_factors,
        scenarios=scenarios,
    )
    selected_routes = tuple(sorted({row.route for row in rows}))
    rows_by_hour: dict[int, list[ResponseRow]] = defaultdict(list)
    rows_by_route: dict[int, list[ResponseRow]] = defaultdict(list)
    for row in rows:
        rows_by_hour[row.ts.hour].append(row)
        rows_by_route[row.route].append(row)

    hours = tuple(
        _build_hour(day, hour, rows_by_hour[hour], len(selected_routes))
        for hour in range(24)
    )
    loads = {
        load.route: load
        for load in service.route_loads(
            day,
            list(selected_routes),
            settings,
            model_factors=model_factors,
            scenarios=scenarios,
        )
    }
    route_analytics = tuple(
        _build_route(
            route,
            rows_by_route[route],
            loads.get(route),
        )
        for route in selected_routes
    )
    return ForecastAnalytics(day, selected_routes, hours, route_analytics)


def _build_hour(
    day: date,
    hour: int,
    rows: list[ResponseRow],
    total_routes: int,
):
    parts = [_row_parts(row) for row in rows]
    actual_values = [actual for actual, _ in parts if actual is not None]
    forecast_values = [forecast for _, forecast in parts if forecast is not None]
    available_routes = sum(
        actual is not None or forecast is not None for actual, forecast in parts
    )
    actual = sum(actual_values) if actual_values else None
    forecast = sum(forecast_values) if forecast_values else None
    total = (
        sum(actual_values) + sum(forecast_values)
        if actual_values or forecast_values
        else None
    )
    return AnalyticsHour(
        ts=datetime.combine(day, time(hour)),
        actual=actual,
        forecast=forecast,
        total=total,
        available_routes=available_routes,
        total_routes=total_routes,
    )


def _build_route(
    route: int,
    rows: list[ResponseRow],
    load: RouteLoad | None,
):
    values_by_hour: dict[int, float | None] = {}
    sources_by_hour: dict[int, Source | None] = {}
    actual_total = 0.0
    forecast_total = 0.0
    for row in rows:
        sources_by_hour[row.ts.hour] = row.source
        actual, forecast = _row_parts(row)
        if actual is None and forecast is None:
            values_by_hour[row.ts.hour] = None
            continue
        actual_total += actual or 0
        forecast_total += forecast or 0
        values_by_hour[row.ts.hour] = (actual or 0) + (forecast or 0)

    hourly = tuple(values_by_hour.get(hour) for hour in range(24))
    hourly_sources = tuple(sources_by_hour.get(hour) for hour in range(24))
    available = [
        (hour, value) for hour, value in enumerate(hourly) if value is not None
    ]
    total = actual_total + forecast_total if available else None
    peak_hour, peak_value = (
        max(available, key=lambda item: item[1]) if available else (None, None)
    )
    norm = load.norm if load is not None else None
    ratio = (
        total / norm.median if total is not None and norm and norm.median > 0 else None
    )
    return AnalyticsRoute(
        route=route,
        hourly=hourly,
        hourly_sources=hourly_sources,
        actual=actual_total,
        forecast=forecast_total,
        total=total,
        peak_hour=peak_hour,
        peak_value=peak_value,
        ratio=ratio,
        deviation_percent=(ratio - 1) * 100 if ratio is not None else None,
        load_level=load.level if load is not None else None,
        norm_median=norm.median if norm is not None else None,
        norm_days=norm.days if norm is not None else 0,
    )


def _row_parts(row: ResponseRow):
    if row.source == "actual":
        return float(row.value) if row.value is not None else None, None
    if row.source in {"forecast", "forecast_seasonal"}:
        return None, row.yhat
    if row.source == "mixed":
        return (
            float(row.value) if row.value is not None else None,
            row.yhat,
        )
    return None, None
