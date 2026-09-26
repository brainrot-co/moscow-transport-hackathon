import logging

import numpy as np
import pandas as pd

from mtml.covariates import (
    CALENDAR,
    DAY_TYPE,
    HOLIDAY_PROXIMITY,
    HOLIDAY_PROXIMITY_MAX,
    SCHOOL,
)
from mtml.forecasters.base import Forecaster

log = logging.getLogger(__name__)

# фактор выключается целиком: holiday — все отклонения производственного календаря от обычной
# недели (праздники, переносы, сокращённые и соседние с праздником дни), одним слайдером
FACTORS = {
    "holiday": CALENDAR + DAY_TYPE + HOLIDAY_PROXIMITY,
    "school_holiday": SCHOOL,
}

# рост пассажиропотока в праздник сильнее этого — подозрительно, но публикацию не блокирует
SUSPICIOUS_HOLIDAY_EFFECT = np.log(1.1)
COLUMNS = ["route", "date", "factor", "log_effect", "yhat_without"]


def neutralize(covariates: pd.DataFrame, factor: str, start: pd.Timestamp, end: pd.Timestamp):
    """Копия ковариат, где на горизонте фактор выключен; история не меняется."""
    neutral = covariates.copy()
    horizon = neutral["ts"].between(start, end + pd.Timedelta(hours=23))
    dow = neutral.loc[horizon, "ts"].dt.dayofweek
    values: dict[str, object] = {column: 0 for column in FACTORS[factor]}
    if factor == "holiday":
        values |= {
            "is_non_working": (dow >= 5).astype(int),
            "day_type": np.select([dow == 5, dow == 6], ["saturday", "sunday"], "workday"),
            "days_to_holiday": HOLIDAY_PROXIMITY_MAX,
            "days_after_holiday": HOLIDAY_PROXIMITY_MAX,
        }
    for column, value in values.items():
        if column in neutral.columns:
            neutral.loc[horizon, column] = value
    return neutral


def daily_totals(frame: pd.DataFrame):
    return frame.groupby(["route", frame["ts"].dt.normalize().rename("date")])["yhat"].sum()


def compute_effects(
    forecaster: Forecaster, forecasts: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
):
    """Контрольные прогоны без каждого фактора: log_effect = log(с фактором) − log(без него)."""
    table = getattr(forecaster, "covariates", None)
    used = set(getattr(forecaster, "future_covariates", ()))
    base = daily_totals(forecasts)
    effects = [pd.DataFrame(columns=COLUMNS)]
    for factor, columns in FACTORS.items():
        touched = [c for c in columns if c in used]
        if table is None or not touched:
            continue
        neutral = neutralize(table, factor, start, end)
        changed = (neutral[touched] != table[touched]).any(axis=1)
        dates = set(neutral.loc[changed, "ts"].dt.normalize())
        if not dates:
            continue
        # тот же прогноз с той же историей, отличаются только ковариаты горизонта
        forecaster.covariates = neutral
        try:
            without = daily_totals(forecaster.predict(start, end))
        finally:
            forecaster.covariates = table

        both = pd.DataFrame({"with": base, "without": without}).dropna().reset_index()
        both["log_effect"] = np.log1p(both["with"]) - np.log1p(both["without"])
        other_days = both[~both["date"].isin(dates)]
        log.info(
            "Фактор %s: %d дней, влияние на остальные дни до %.1f%%",
            factor,
            len(dates),
            100 * (np.exp(other_days["log_effect"].abs().max()) - 1),
        )
        effect = both[both["date"].isin(dates)].assign(factor=factor)
        effects.append(effect.rename(columns={"without": "yhat_without"})[COLUMNS])
        if factor == "holiday":
            warn_suspicious(effect, table, start, end)
    result = pd.concat(effects, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"])
    return result.astype({"route": "int16", "log_effect": "float64", "yhat_without": "float64"})


def warn_suspicious(
    effect: pd.DataFrame, table: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
):
    horizon = table[table["ts"].between(start, end + pd.Timedelta(hours=23))]
    holidays = set(horizon.loc[horizon["is_holiday_weekday"] == 1, "ts"].dt.normalize())
    odd = effect[effect["date"].isin(holidays) & (effect["log_effect"] > SUSPICIOUS_HOLIDAY_EFFECT)]
    for row in odd.itertuples():
        log.warning(
            "Праздник %s, маршрут %s: модель закладывает рост на %.0f%%",
            row.date.date(),
            row.route,
            100 * (np.exp(row.log_effect) - 1),
        )
