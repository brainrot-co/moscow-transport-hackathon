from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

DayKind = Literal["workday", "day_off"]
LoadLevel = Literal["low", "medium", "high"]

# pre_holiday и post_holiday — рабочие дни, у них норма будней
DAY_OFF_TYPES = frozenset({"saturday", "sunday", "holiday"})


@dataclass(frozen=True, slots=True)
class LoadNormSettings:
    weeks: int
    min_days: int
    low_quantile: float
    high_quantile: float
    min_deviation: float


@dataclass(frozen=True, slots=True)
class LoadNorm:
    days: int
    date_from: date
    date_to: date
    low: float
    median: float
    high: float

    def level(self, value: float) -> LoadLevel:
        if value < self.low:
            return "low"
        if value > self.high:
            return "high"
        return "medium"


def day_kind(day: date, day_types: dict[date, str]) -> DayKind:
    day_type = day_types.get(day)
    if day_type is None:
        # вне календаря праздников не знаем, отличаем только субботу и воскресенье
        return "day_off" if day.weekday() >= 5 else "workday"
    return "day_off" if day_type in DAY_OFF_TYPES else "workday"


def route_norm(
    totals: dict[date, int],
    kind: DayKind,
    day_types: dict[date, str],
    watermark: date,
    settings: LoadNormSettings,
) -> LoadNorm | None:
    same_kind = sorted(
        (day, total)
        for day, total in totals.items()
        if day <= watermark and day_kind(day, day_types) == kind
    )
    window_start = watermark - timedelta(weeks=settings.weeks)
    recent = [(day, total) for day, total in same_kind if day > window_start]
    # после долгого простоя в окне мало дней: берём всю историю того же вида дня
    sample = recent if len(recent) >= settings.min_days else same_kind
    if len(sample) < settings.min_days:
        return None
    values = sorted(total for _, total in sample)
    median = _quantile(values, 0.5)
    # у стабильного маршрута p25–p75 — это ±3%, и обычный день красился бы как аномалия
    return LoadNorm(
        days=len(values),
        date_from=sample[0][0],
        date_to=sample[-1][0],
        low=min(
            _quantile(values, settings.low_quantile),
            median * (1 - settings.min_deviation),
        ),
        median=median,
        high=max(
            _quantile(values, settings.high_quantile),
            median * (1 + settings.min_deviation),
        ),
    )


def _quantile(values: list[int], q: float) -> float:
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)
