from datetime import date, datetime, timedelta

from app.ml.load import LoadNormSettings, day_kind, route_norm
from app.ml.models import ActualRecord, ForecastRecord, ForecastSnapshot
from app.services.forecast import ForecastService

SETTINGS = LoadNormSettings(
    weeks=8, min_days=10, low_quantile=0.25, high_quantile=0.75, min_deviation=0.1
)
WATERMARK = date(2025, 10, 31)


def daily(days: int, workday: int, day_off: int) -> dict[date, int]:
    start = WATERMARK - timedelta(days=days - 1)
    return {
        start + timedelta(days=offset): (
            day_off if (start + timedelta(days=offset)).weekday() >= 5 else workday
        )
        for offset in range(days)
    }


def test_calendar_overrides_weekday():
    day_types = {date(2025, 11, 4): "holiday", date(2025, 11, 1): "pre_holiday"}

    assert day_kind(date(2025, 11, 4), day_types) == "day_off"
    assert day_kind(date(2025, 11, 1), day_types) == "workday"
    assert day_kind(date(2025, 11, 8), {}) == "day_off"


def test_norm_uses_only_same_day_kind():
    totals = daily(56, workday=20000, day_off=8000)

    workday = route_norm(totals, "workday", {}, WATERMARK, SETTINGS)
    day_off = route_norm(totals, "day_off", {}, WATERMARK, SETTINGS)

    assert workday is not None and workday.median == 20000
    assert day_off is not None and day_off.median == 8000
    assert workday.days == 40 and day_off.days == 16


def test_norm_ignores_days_outside_window():
    totals = daily(120, workday=20000, day_off=8000)
    for day in list(totals)[:60]:
        totals[day] //= 2

    norm = route_norm(totals, "workday", {}, WATERMARK, SETTINGS)

    assert norm is not None
    assert norm.median == 20000
    assert norm.date_from > WATERMARK - timedelta(weeks=8)


def test_short_history_falls_back_to_whole_period_or_none():
    totals = daily(120, workday=20000, day_off=8000)
    gap = date(2025, 10, 1)
    recent_gap = {day: total for day, total in totals.items() if day < gap}

    fallback = route_norm(recent_gap, "workday", {}, WATERMARK, SETTINGS)
    empty = route_norm(daily(7, 20000, 8000), "workday", {}, WATERMARK, SETTINGS)

    assert fallback is not None and fallback.date_to < gap
    assert empty is None


def test_level_is_relative_to_route_own_norm():
    small = daily(56, workday=5000, day_off=3000)
    small.update({day: 4000 + day.day * 50 for day in small if day.weekday() < 5})
    norm = route_norm(small, "workday", {}, WATERMARK, SETTINGS)

    assert norm is not None
    assert norm.level(norm.high + 1) == "high"
    assert norm.level(norm.median) == "medium"
    assert norm.level(norm.low - 1) == "low"


def test_route_loads_sum_actuals_and_forecast():
    day = date(2025, 11, 5)
    history = {
        (7, datetime.combine(past, datetime.min.time())): ActualRecord(
            7, datetime.combine(past, datetime.min.time()), total
        )
        for past, total in daily(56, workday=100, day_off=40).items()
    }
    midnight = datetime(2025, 11, 5)
    history[(7, midnight)] = ActualRecord(7, midnight, 30)
    forecast = {
        (7, midnight.replace(hour=hour)): ForecastRecord(
            7, midnight.replace(hour=hour), 10
        )
        for hour in range(1, 24)
    }
    snapshot = ForecastSnapshot(
        actuals=history,
        short=forecast,
        year={},
        watermark=day,
        daily_actuals={7: daily(56, workday=100, day_off=40)},
    )

    [load] = ForecastService(snapshot).route_loads(day, [7], SETTINGS)

    assert load.value == 30 + 23 * 10
    assert load.level == "high"


def test_stable_route_keeps_small_deviation_medium():
    totals = daily(56, workday=20000, day_off=8000)

    norm = route_norm(totals, "workday", {}, WATERMARK, SETTINGS)

    assert norm is not None
    assert norm.level(20000 * 0.95) == "medium"
    assert norm.level(20000 * 0.85) == "low"
    assert norm.level(20000 * 1.15) == "high"
