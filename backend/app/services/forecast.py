from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.ml.aggregation import Granularity, aggregate_rows
from app.ml.corrections import Scenario, apply_corrections
from app.ml.models import ForecastSnapshot, ResponseRow


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
                result.append(self.snapshot.resolve(route, timestamp))
            timestamp += timedelta(hours=1)
        corrected = apply_corrections(
            result,
            self.snapshot.effects,
            model_factors=model_factors,
            scenarios=scenarios,
        )
        return aggregate_rows(corrected, granularity)


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
    return (
        value.astimezone(ZoneInfo("Europe/Moscow"))
        .replace(tzinfo=None, minute=0, second=0, microsecond=0)
    )
