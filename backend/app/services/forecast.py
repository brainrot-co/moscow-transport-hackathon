from __future__ import annotations

from datetime import datetime, timedelta

from app.ml.aggregation import Granularity, aggregate_rows
from app.ml.corrections import Scenario, apply_corrections
from app.ml.models import ForecastSnapshot, ResponseRow


class ForecastService:
    def __init__(self, snapshot: ForecastSnapshot | None):
        self.snapshot = snapshot

    def meta(self, error: str | None = None) -> dict[str, object]:
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
        timestamp = date_from
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
    return [row.as_dict() for row in rows]