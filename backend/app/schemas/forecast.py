from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .scenario import ScenarioBase


class ForecastRowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: int
    ts: datetime
    source: Literal["actual", "forecast", "forecast_seasonal", "mixed"] | None
    value: int | None
    yhat_model: float | None
    yhat: float | None
    q10: float | None
    q90: float | None
    estimated: bool = False
    applied: list[dict[str, object]] = Field(default_factory=list)
    availability: str | None = None


class ForecastMetaRead(BaseModel):
    schema_version: int = 1
    available: bool
    short_run_id: str | None = None
    year_run_id: str | None = None
    watermark: date | None = None
    data_cutoff: date | None = None
    now: datetime | None = None
    published_at: datetime | None = None
    stale: bool = False
    cold_start_routes: list[int] = Field(default_factory=list)
    model: dict[str, str | None] = Field(default_factory=dict)
    error: str | None = None


class ForecastQueryRead(BaseModel):
    date_from: datetime
    date_to: datetime
    granularity: Literal["hour", "day", "week", "month"]


class ForecastResponse(BaseModel):
    schema_version: int = 1
    query: ForecastQueryRead
    data: list[ForecastRowRead]
    meta: ForecastMetaRead


class RouteLoadRead(BaseModel):
    route: int
    value: float | None
    load_level: Literal["low", "medium", "high"] | None
    ratio: float | None
    norm_low: float | None
    norm_median: float | None
    norm_high: float | None
    norm_days: int = 0
    norm_from: date | None = None
    norm_to: date | None = None


class RouteLoadResponse(BaseModel):
    schema_version: int = 1
    date: date
    day_kind: Literal["workday", "day_off"]
    day_type: str | None
    norm_weeks: int
    low_quantile: float
    high_quantile: float
    min_deviation: float
    data: list[RouteLoadRead]
    meta: ForecastMetaRead


class ForecastPreviewRequest(BaseModel):
    date_from: datetime
    date_to: datetime
    routes: list[int] | None = None
    granularity: Literal["hour", "day", "week", "month"] = "hour"
    model_factors: dict[str, float] = Field(default_factory=dict)
    draft: list[ScenarioBase] = Field(default_factory=list)
