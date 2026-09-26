import logging

import numpy as np
import pandas as pd

from mtml.forecasters.base import check_contiguous, horizon_hours
from mtml.forecasters.chronos2 import default_device, load_pipeline

log = logging.getLogger(__name__)

MODEL_ID = "amazon/chronos-2"
DAILY_CALENDAR = ("is_non_working", "is_holiday_weekday", "dow")
# погода по дням из почасовой: средняя температура, суммы осадков и снега
DAILY_WEATHER = {"temperature": "mean", "precipitation": "sum", "snowfall": "sum"}
# вариант прогноза дневной суммы маршрута: (ковариаты, известные на горизонте; только прошлые)
DailyVariant = tuple[tuple[str, ...], tuple[str, ...]]
DAILY_VARIANTS: tuple[DailyVariant, ...] = (((), ()), (DAILY_CALENDAR, ()))
# маршрут, который по профилю в этот день почти не ходит (маршрут 50 в выходные), остаётся на
# профиле: иначе прогноз суммы размажется по нескольким случайным часам
IDLE_SHARE = 0.05
# с этого числа будни декабря похожи на первые рабочие дни после новогодних праздников
NEW_YEAR_FROM_DAY = 27


class ProfileDailyForecaster:
    """Среднее недельного профиля и прогнозов Chronos-2 по дневным суммам, разложенных по часам
    формой профиля."""

    future_covariates = ("is_non_working", "is_holiday_weekday")

    def __init__(
        self, covariates: pd.DataFrame, variants: tuple[DailyVariant, ...] = DAILY_VARIANTS
    ):
        self.covariates = covariates
        self.variants = variants
        self.device = default_device()
        self.name = "profile_daily"

    def fit(self, history: pd.DataFrame):
        self.history = history
        return self

    def predict(self, start: str | pd.Timestamp, end: str | pd.Timestamp):
        check_contiguous(self.history, start)
        wide = self.history.pivot(index="ts", columns="route", values="y")
        routes = wide.columns.to_numpy()
        past_days = wide.index[::24]
        hourly = wide.to_numpy().reshape(len(past_days), 24, len(routes))
        days = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
        features = day_features(self.covariates)
        past, future = features.loc[past_days], features.loc[days]

        profile = weekly_profile(hourly, past, future)
        totals = hourly.sum(axis=1)
        special = future["special"].to_numpy() == 1
        parts = [profile]
        for future_columns, past_columns in self.variants:
            forecast = self._daily_totals(
                totals, routes, features, past_days, days, future_columns, past_columns
            )
            parts.append(spread_over_hours(profile, forecast, special))
        result = sum(np.clip(part, 0, None) for part in parts) / len(parts)

        late_december = (
            (days.month == 12)
            & (days.day >= NEW_YEAR_FROM_DAY)
            & (future["dow"].to_numpy() < 5)
            & (future["is_non_working"].to_numpy() == 0)
        )
        if late_december.any():
            factor = new_year_factor(totals, past)
            if factor is None:
                log.warning("В истории нет января: конец декабря без поправки на Новый год")
            else:
                result[late_december] *= factor

        return pd.DataFrame(
            {
                "route": np.tile(routes, len(days) * 24),
                "ts": np.repeat(horizon_hours(start, end), len(routes)),
                "yhat": result.reshape(-1),
            }
        ).sort_values(["route", "ts"], ignore_index=True)

    def _daily_totals(
        self,
        totals: np.ndarray,
        routes: np.ndarray,
        features: pd.DataFrame,
        past_days: pd.DatetimeIndex,
        days: pd.DatetimeIndex,
        future_columns: tuple[str, ...],
        past_columns: tuple[str, ...],
    ):
        """Прогноз Chronos-2 дневной суммы посадок маршрута, [день, маршрут]."""
        columns = [*future_columns, *past_columns]
        missing = [c for c in columns if c not in features.columns]
        if missing:
            raise ValueError(f"В ковариатах нет колонок {missing}")
        gaps = features.loc[past_days, columns].isna().any().any() or (
            features.loc[days, list(future_columns)].isna().any().any()
        )
        if gaps:
            raise ValueError(f"Нет значений ковариат {columns} на истории или горизонте прогноза")
        ids = routes.astype(str)
        context = pd.DataFrame(
            {
                "item_id": np.repeat(ids, len(past_days)),
                "timestamp": np.tile(past_days, len(routes)),
                "y": totals.T.reshape(-1),
            }
        ).join(features[columns], on="timestamp")
        future = None
        if future_columns:
            future = pd.DataFrame(
                {"item_id": np.repeat(ids, len(days)), "timestamp": np.tile(days, len(routes))}
            ).join(features[list(future_columns)], on="timestamp")
        raw = load_pipeline(MODEL_ID, self.device).predict_df(
            context,
            future_df=future,
            id_column="item_id",
            timestamp_column="timestamp",
            target="y",
            prediction_length=len(days),
            quantile_levels=[0.5],
            freq="D",
        )
        return raw.pivot(index="timestamp", columns="item_id", values="0.5")[ids].to_numpy()


def day_features(covariates: pd.DataFrame):
    hourly = covariates.drop_duplicates("ts").set_index("ts")
    days = hourly.loc[hourly.index.hour == 0, ["is_non_working", "is_holiday_weekday"]]
    dow = days.index.dayofweek
    work_weekend = ((days["is_non_working"] == 0) & (dow >= 5)).astype(int)
    days = days.assign(
        dow=dow, work_weekend=work_weekend, special=days["is_holiday_weekday"] | work_weekend
    )
    if not set(DAILY_WEATHER) <= set(hourly.columns):
        return days
    by_day = hourly[list(DAILY_WEATHER)].groupby(hourly.index.normalize())
    # день без полной погоды — пропуск, а не нулевые осадки
    weather = by_day.agg(DAILY_WEATHER).where(by_day.count() == 24)
    return days.join(weather)


def weekly_profile(hourly: np.ndarray, past: pd.DataFrame, future: pd.DataFrame):
    """[день, час, маршрут]. Уровень дня — медиана Пн–Чт последней недели × коэффициент дня недели
    за 6 недель, доли часов — за 4 недели; праздники и рабочие выходные в расчёт не идут.
    В прогнозе праздник — как воскресенье, рабочая суббота — среднее пятницы и субботы."""
    totals = hourly.sum(axis=1)
    dow = past["dow"].to_numpy()
    regular = past["special"].to_numpy() == 0
    age = len(past) - np.arange(len(past))
    mon_thu = regular & (dow <= 3)

    anchor = np.median(totals[mon_thu & (age <= 7)], axis=0)
    reference = np.maximum(np.median(totals[mon_thu & (age <= 42)], axis=0), 1)
    typical = np.zeros((7, 24, hourly.shape[2]))
    for d in range(7):
        level = anchor * np.median(totals[regular & (dow == d) & (age <= 42)], axis=0) / reference
        shape_days = (mon_thu if d <= 3 else regular & (dow == d)) & (age <= 28)
        hours = hourly[shape_days].sum(axis=0)
        typical[d] = hours / np.maximum(hours.sum(axis=0), 1) * level

    profile = typical[np.where(future["is_holiday_weekday"] == 1, 6, future["dow"])]
    profile[future["work_weekend"].to_numpy() == 1] = (typical[4] + typical[5]) / 2
    return profile


def spread_over_hours(profile: np.ndarray, day_totals: np.ndarray, special: np.ndarray):
    """В праздники, рабочие выходные и дни простоя маршрута остаётся сумма профиля."""
    profile_totals = profile.sum(axis=1)
    totals = np.clip(day_totals, 0, None)
    keep = special[:, None] | (profile_totals < IDLE_SHARE * np.maximum(totals, 1))
    totals = np.where(keep, profile_totals, totals)
    return profile / np.maximum(profile_totals[:, None, :], 1e-9) * totals[:, None, :]


def new_year_factor(totals: np.ndarray, past: pd.DataFrame):
    """Первые два рабочих дня последнего января истории к тем же дням недели трёх следующих
    недель; None, если такого января в истории нет."""
    daily = pd.Series(totals.sum(axis=1), index=past.index)
    last = past.index.max()
    work = past[(past.index.month == 1) & (past["is_non_working"] == 0) & (past["dow"] < 5)].index
    work = work[work + pd.Timedelta(weeks=3) <= last]
    if work.empty:
        return None
    first = work[work.year == work.year.max()][:2]
    ratios = [
        daily[day] / daily[[day + pd.Timedelta(weeks=k) for k in (1, 2, 3)]].median()
        for day in first
    ]
    return float(np.mean(ratios))
