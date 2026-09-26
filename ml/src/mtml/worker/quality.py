import pandas as pd

from mtml.forecasters.base import horizon_hours

# недельная сумма прогноза должна быть в этих пределах от медианы недель в недавней истории
WEEKLY_TOTAL_RANGE = (0.3, 3.0)

# ни один день прогноза не должен превышать столько максимальных дней недавней истории
DAILY_MAX_FACTOR = 3.0
RECENT_WEEKS = 4


class QualityError(ValueError):
    """Прогноз не прошёл проверки: он не публикуется, остаётся прежний."""


def check_forecast(
    forecasts: pd.DataFrame,
    history: pd.DataFrame,
    routes: tuple[int, ...],
    start: pd.Timestamp,
    end: pd.Timestamp,
):
    """
    Проверки перед публикацией; при любой ошибке прогон не публикуется.
    """
    failures = []
    expected_rows = len(routes) * len(horizon_hours(start, end))
    if len(forecasts) != expected_rows or forecasts.duplicated(["route", "ts"]).any():
        failures.append(f"сетка: {len(forecasts)} строк вместо {expected_rows}")
    if forecasts["yhat"].isna().any():
        failures.append(f"пропуски: {int(forecasts['yhat'].isna().sum())} строк без прогноза")
    if (forecasts["yhat"] < 0).any():
        failures.append("отрицательные значения")

    recent = history[history["ts"] > history["ts"].max() - pd.Timedelta(weeks=RECENT_WEEKS)]
    recent_daily = recent.groupby(["route", recent["ts"].dt.normalize()])["y"].sum()
    daily = forecasts.groupby(["route", forecasts["ts"].dt.normalize()])["yhat"].sum()
    full_weeks = ((end - start).days + 1) // 7
    low, high = WEEKLY_TOTAL_RANGE
    for route, history_days in recent_daily.groupby(level="route"):
        if history_days.sum() == 0:
            continue
        values = history_days.to_numpy()
        usual_week = pd.Series(
            values[-7 * (len(values) // 7) :].reshape(-1, 7).sum(axis=1)
        ).median()
        route_days = daily.loc[route].to_numpy()
        weeks = route_days[: 7 * full_weeks].reshape(-1, 7).sum(axis=1) / usual_week
        if not ((weeks >= low) & (weeks <= high)).all():
            failures.append(
                f"маршрут {route}: недельные суммы от {weeks.min():.2f} до {weeks.max():.2f} "
                f"медианы последних {RECENT_WEEKS} недель"
            )
        if route_days.max() > DAILY_MAX_FACTOR * values.max():
            failures.append(f"маршрут {route}: день прогноза больше {DAILY_MAX_FACTOR}× максимума")

    if failures:
        raise QualityError("; ".join(failures))
    return {
        "grid": "ok",
        "no_nan": "ok",
        "non_negative": "ok",
        "weekly_totals": "ok",
        "daily_max": "ok",
    }
