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
    stale: bool = False
    error: str | None = None


class ForecastQueryRead(BaseModel):
    date_from: datetime
    date_to: datetime
    granularity: Literal["hour"]


class ForecastResponse(BaseModel):
    schema_version: int = 1
    query: ForecastQueryRead
    data: list[ForecastRowRead]
    meta: ForecastMetaRead


class ForecastPreviewRequest(BaseModel):
    date_from: datetime
    date_to: datetime
    routes: list[int] | None = None
    model_factors: dict[str, float] = Field(default_factory=dict)
    draft: list[ScenarioBase] = Field(default_factory=list)