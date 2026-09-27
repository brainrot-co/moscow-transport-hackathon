from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

Source = Literal["actual", "forecast", "forecast_seasonal", "mixed"]


class SnapshotError(ValueError):
    """Raised when an ML snapshot cannot satisfy the backend contract."""


@dataclass(frozen=True, slots=True)
class ActualRecord:
    route: int
    ts: datetime
    value: int
    status: str = "final"


@dataclass(frozen=True, slots=True)
class ForecastRecord:
    route: int
    ts: datetime
    yhat: float
    q10: float | None = None
    q90: float | None = None


@dataclass(frozen=True, slots=True)
class ResponseRow:
    route: int
    ts: datetime
    source: Source | None
    value: int | None
    yhat_model: float | None
    yhat: float | None
    q10: float | None
    q90: float | None
    estimated: bool = False
    applied: tuple[dict[str, object], ...] = field(default_factory=tuple)
    availability: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "route": self.route,
            "ts": self.ts.isoformat(),
            "source": self.source,
            "value": self.value,
            "yhat_model": self.yhat_model,
            "yhat": self.yhat,
            "q10": self.q10,
            "q90": self.q90,
            "estimated": self.estimated,
            "applied": list(self.applied),
        }
        if self.availability is not None:
            result["availability"] = self.availability
        return result


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    kind: Literal["short", "year"]
    schema_version: int
    data_cutoff: date
    step: str
    routes: frozenset[int]
    timezone: str = "Europe/Moscow"
    cold_start_routes: frozenset[int] = field(default_factory=frozenset)
    model_name: str | None = None


@dataclass(frozen=True, slots=True)
class ForecastSnapshot:
    actuals: dict[tuple[int, datetime], ActualRecord]
    short: dict[tuple[int, datetime], ForecastRecord]
    year: dict[tuple[int, datetime], ForecastRecord]
    effects: dict[tuple[int, date, str], float] = field(default_factory=dict)
    short_meta: RunMetadata | None = None
    year_meta: RunMetadata | None = None
    watermark: date | None = None
    day_types: dict[date, str] = field(default_factory=dict)
    daily_actuals: dict[int, dict[date, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_runs()

    def _validate_runs(self) -> None:
        if self.short_meta is None or self.year_meta is None:
            return
        fields_match = (
            self.short_meta.schema_version == self.year_meta.schema_version
            and self.short_meta.step == self.year_meta.step
            and self.short_meta.timezone == self.year_meta.timezone
            and self.short_meta.routes == self.year_meta.routes
            and self.short_meta.data_cutoff == self.year_meta.data_cutoff
        )
        if not fields_match:
            raise SnapshotError("short and year runs are incompatible")

    def resolve(self, route: int, ts: datetime) -> ResponseRow:
        key = (route, ts)
        actual = self.actuals.get(key)
        if (
            actual is not None
            and actual.status == "final"
            and (self.watermark is None or ts.date() <= self.watermark)
        ):
            return ResponseRow(
                route=route,
                ts=ts,
                source="actual",
                value=actual.value,
                yhat_model=None,
                yhat=None,
                q10=None,
                q90=None,
            )

        cold_start_routes = (
            (self.short_meta.cold_start_routes if self.short_meta else frozenset())
            | (self.year_meta.cold_start_routes if self.year_meta else frozenset())
        )
        if route in cold_start_routes:
            return ResponseRow(
                route=route,
                ts=ts,
                source=None,
                value=None,
                yhat_model=None,
                yhat=None,
                q10=None,
                q90=None,
                availability="cold_start",
            )

        short = self.short.get(key)
        if short is not None:
            return ResponseRow(
                route=route,
                ts=ts,
                source="forecast",
                value=None,
                yhat_model=short.yhat,
                yhat=short.yhat,
                q10=short.q10,
                q90=short.q90,
            )

        year = self.year.get(key)
        if year is not None:
            return ResponseRow(
                route=route,
                ts=ts,
                source="forecast_seasonal",
                value=None,
                yhat_model=year.yhat,
                yhat=year.yhat,
                q10=year.q10,
                q90=year.q90,
            )

        return ResponseRow(
            route=route,
            ts=ts,
            source=None,
            value=None,
            yhat_model=None,
            yhat=None,
            q10=None,
            q90=None,
            availability="unavailable",
        )
