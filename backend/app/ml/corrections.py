from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from .models import ResponseRow


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    kind: Literal["model_factor", "scenario"]
    factor: str
    value: float
    date_from: date
    date_to: date
    routes: frozenset[int] | None = None
    days: Literal["all", "weekdays", "weekends"] = "all"
    hour_from: int | None = None
    hour_to: int | None = None
    title: str | None = None

    def applies(self, route: int, timestamp: datetime) -> bool:
        if route not in self.routes if self.routes is not None else False:
            return False
        if not self.date_from <= timestamp.date() <= self.date_to:
            return False
        if self.days == "weekdays" and timestamp.weekday() >= 5:
            return False
        if self.days == "weekends" and timestamp.weekday() < 5:
            return False
        if self.hour_from is not None and timestamp.hour < self.hour_from:
            return False
        if self.hour_to is not None and timestamp.hour > self.hour_to:
            return False
        return True


def apply_corrections(
    rows: list[ResponseRow],
    effects: dict[tuple[int, date, str], float],
    model_factors: dict[str, float] | None = None,
    scenarios: list[Scenario] | None = None,
) -> list[ResponseRow]:
    model_factors = model_factors or {}
    scenarios = scenarios or []
    corrected: list[ResponseRow] = []

    for row in rows:
        if row.source == "actual" or row.yhat_model is None:
            corrected.append(row)
            continue

        multiplier = 1.0
        applied: list[dict[str, object]] = []
        for factor, strength in model_factors.items():
            if strength == 1.0:
                continue
            log_effect = effects.get((row.route, row.ts.date(), factor))
            if log_effect is None:
                continue
            factor_multiplier = math.exp(log_effect * (strength - 1.0))
            multiplier *= factor_multiplier
            applied.append(
                {
                    "kind": "model_factor",
                    "factor": factor,
                    "value": strength,
                    "multiplier": factor_multiplier,
                }
            )

        for scenario in scenarios:
            if scenario.kind != "scenario" or not scenario.applies(row.route, row.ts):
                continue
            multiplier *= scenario.value
            applied.append(
                {
                    "id": scenario.id,
                    "kind": "scenario",
                    "factor": scenario.factor,
                    "value": scenario.value,
                    "title": scenario.title,
                }
            )

        corrected.append(
            ResponseRow(
                route=row.route,
                ts=row.ts,
                source=row.source,
                value=None,
                yhat_model=row.yhat_model,
                yhat=max(row.yhat_model * multiplier, 0.0),
                q10=_scale(row.q10, multiplier),
                q90=_scale(row.q90, multiplier),
                estimated=row.estimated,
                applied=tuple(applied),
                availability=row.availability,
            )
        )
    return corrected


def _scale(value: float | None, multiplier: float) -> float | None:
    return None if value is None else max(value * multiplier, 0.0)