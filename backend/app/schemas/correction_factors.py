from typing import Literal

from pydantic import BaseModel, ConfigDict


class FactorSource(BaseModel):
    title: str
    url: str
    finding: str


class LocalCheck(BaseModel):
    # проверку по истории пишет ml/scripts/check_correction_factors.py,
    # набор полей у разных типов событий разный
    model_config = ConfigDict(extra="allow")

    name: str
    effect: float | None
    n: int
    unit: str


class ModelFactorRead(BaseModel):
    factor: str
    label: str
    min: float
    max: float
    step: float
    default: float
    estimate: str


class ScenarioTypeRead(BaseModel):
    type: str
    label: str
    scope: Literal["city", "routes"]
    default_multiplier: float
    min: float
    max: float
    estimate: str
    sources: list[FactorSource]
    local_check: list[LocalCheck] | None


class CorrectionFactorsRead(BaseModel):
    schema_version: int
    model_factors: list[ModelFactorRead]
    scenario_types: list[ScenarioTypeRead]

    def validate_scenario(
        self,
        kind: str,
        factor: str,
        value: float,
        routes: list[int] | None,
        check_scope: bool = True,
    ) -> str | None:
        """Код ошибки для сценария, который противоречит справочнику, или None."""
        if kind == "model_factor":
            model_factor = next(
                (f for f in self.model_factors if f.factor == factor), None
            )
            if model_factor is None:
                return "unknown_model_factor"
            bounds = (model_factor.min, model_factor.max)
        else:
            scenario_type = next(
                (t for t in self.scenario_types if t.type == factor), None
            )
            if scenario_type is None:
                return "unknown_scenario_type"
            if check_scope and scenario_type.scope == "city" and routes:
                return "city_scenario_cannot_target_routes"
            if check_scope and scenario_type.scope == "routes" and not routes:
                return "route_scenario_requires_routes"
            bounds = (scenario_type.min, scenario_type.max)
        if not bounds[0] <= value <= bounds[1]:
            return "value_out_of_reference_range"
        return None
