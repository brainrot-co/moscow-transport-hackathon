from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ScenarioBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["model_factor", "scenario"]
    factor: str = Field(min_length=1, max_length=64)
    value: float = Field(ge=0, le=2)
    routes: list[int] | None = None
    date_from: date
    date_to: date
    days: Literal["all", "weekdays", "weekends"] = "all"
    hour_from: int | None = Field(default=None, ge=0, le=23)
    hour_to: int | None = Field(default=None, ge=0, le=23)
    title: str | None = Field(default=None, max_length=255)
    comment: str | None = Field(default=None, max_length=2000)
    source_url: HttpUrl | None = None
    active: bool = True

    @model_validator(mode="after")
    def validate_range(self):
        if self.date_to < self.date_from:
            raise ValueError("date_to must not precede date_from")
        if (
            self.hour_from is not None
            and self.hour_to is not None
            and self.hour_to < self.hour_from
        ):
            raise ValueError("hour_to must not precede hour_from")
        if self.kind == "model_factor" and self.routes:
            raise ValueError("model factors have city scope and cannot target routes")
        return self


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | None = Field(default=None, ge=0, le=2)
    date_from: date | None = None
    date_to: date | None = None
    days: Literal["all", "weekdays", "weekends"] | None = None
    hour_from: int | None = Field(default=None, ge=0, le=23)
    hour_to: int | None = Field(default=None, ge=0, le=23)
    title: str | None = Field(default=None, max_length=255)
    comment: str | None = Field(default=None, max_length=2000)
    source_url: HttpUrl | None = None
    active: bool | None = None


class ScenarioRead(ScenarioBase):
    id: int
    created_by: int
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, scenario):
        data = {
            **{
                field: getattr(scenario, field)
                for field in ScenarioBase.model_fields
            },
            "id": scenario.id,
            "created_by": scenario.created_by,
            "created_at": scenario.created_at.isoformat(),
            "updated_at": scenario.updated_at.isoformat(),
        }
        return cls.model_validate(data)