"""Прогноз почасовых посадок трамваев на 2025-11-01..2025-12-31 (WAPE-score на лидерборде 0.88359).

Запуск из корня репозитория:  python -m ml.predict [путь/к/dataset.zip]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from chronos import Chronos2Pipeline

from ml.parsing import load_external_data
from ml.preprocessing import build_day_features, load_dataset

ML_DIR = Path(__file__).resolve().parent
DATASET_PATH = ML_DIR / "data" / "dataset.zip"
CACHE_DIR = ML_DIR / "data" / "external"
OUTPUT_PATH = ML_DIR / "output" / "submission.csv"
FORECAST_DAYS = pd.date_range("2025-11-01", "2025-12-31", freq="D")

# ковариаты — признаки дня, известные на весь горизонт прогноза
CALENDAR = ["day_off", "holiday", "shortened", "school_quarters", "school_modular"]
DAILY_CALENDAR = ["day_off", "holiday", "dow"]
WEATHER = ["precipitation_sum", "snowfall_sum", "temperature_2m_mean"]


class TramForecaster:
    """Ансамбль zero-shot прогнозов Chronos-2 (без обучения на наших данных). Прогноз — среднее трёх частей:
      RH  — Chronos-2 по 216 суточным рядам «маршрут × час» с календарём и школьными каникулами;
      RHD — то же + тип дня;
      V2  — среднее недельного профиля и трёх прогнозов суточных сумм Chronos-2 (без ковариат / с календарём /
            с календарём и погодой), разложенных по часам формой профиля; 29–30 декабря × коэффициент
            первых рабочих дней после Нового года.
    """

    def __init__(self, hourly: pd.DataFrame, features: pd.DataFrame):
        self.model = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
        self.features = features
        self.routes = list(hourly.columns)
        self.history_days = hourly.index[::24]
        self.history = hourly.to_numpy().reshape(len(self.history_days), 24, len(self.routes))  # [день, час, маршрут]

    def predict(self, days: pd.DatetimeIndex) -> np.ndarray:
        """Прогноз [день, час, маршрут]."""
        rh = self._route_hour(days, CALENDAR)
        rhd = self._route_hour(days, CALENDAR + ["day_type"])

        profile = self._weekly_profile(days)
        v2_parts = [profile]
        for covariates in ([], DAILY_CALENDAR, DAILY_CALENDAR + WEATHER):
            v2_parts.append(self._spread_over_hours(profile, self._daily_totals(days, covariates), days))
        v2 = sum(np.clip(part, 0, None) for part in v2_parts) / 4

        before_new_year = ((days.month == 12) & (days.day >= 27) & (days.dayofweek < 5)
                           & (self.features.loc[days, "day_off"].to_numpy() == 0))
        v2[before_new_year] *= self._new_year_factor()

        return (rh + rhd + v2) / 3

    def _chronos(self, series: dict, covariates: list, days) -> dict:
        """Прогон Chronos-2: {id ряда: история по дням} -> {id ряда: медианный прогноз на days}."""
        known = self.features[covariates].copy()
        if "day_type" in covariates:
            known["day_type"] = known["day_type"].astype(str)  # категориальная ковариата

        history = pd.concat([pd.DataFrame({"id": series_id, "timestamp": self.history_days, "target": values})
                             for series_id, values in series.items()], ignore_index=True)
        history = history.join(known, on="timestamp")
        future = None
        if covariates:
            future = pd.concat([pd.DataFrame({"id": series_id, "timestamp": days}) for series_id in series],
                               ignore_index=True)
            future = future.join(known, on="timestamp")

        forecast = self.model.predict_df(history, future_df=future, prediction_length=len(days),
                                         quantile_levels=[0.5], id_column="id", timestamp_column="timestamp",
                                         target="target")
        return {series_id: group["predictions"].to_numpy() for series_id, group in forecast.groupby("id")}

    def _route_hour(self, days, covariates) -> np.ndarray:
        """Ряд = посадки маршрута в данный час по дням (216 рядов). Недельная сезонность остаётся внутри ряда,
        горизонт 61 шаг — в родном диапазоне модели."""
        series = {f"{route}_{hour}": self.history[:, hour, r]
                  for r, route in enumerate(self.routes) for hour in range(24)}
        forecast = self._chronos(series, covariates, days)

        result = np.zeros((len(days), 24, len(self.routes)))
        for r, route in enumerate(self.routes):
            for hour in range(24):
                result[:, hour, r] = forecast[f"{route}_{hour}"]
        return np.clip(result, 0, None)

    def _daily_totals(self, days, covariates) -> np.ndarray:
        """Прогноз суточной суммы посадок каждого маршрута, [день, маршрут]."""
        totals = self.history.sum(axis=1)
        series = {str(route): totals[:, r] for r, route in enumerate(self.routes)}
        forecast = self._chronos(series, covariates, days)
        return np.stack([forecast[str(route)] for route in self.routes], axis=1)

    def _weekly_profile(self, days) -> np.ndarray:
        """Недельный профиль [день, час, маршрут]. Уровень дня = медиана Пн–Чт последней недели × коэффициент
        дня недели за 6 недель; доли часов — за 4 недели, Пн–Чт вместе. Праздники и рабочие выходные в расчёт
        не берутся; в прогнозе праздник — как воскресенье, рабочая суббота — среднее пятницы и субботы."""
        n_days = len(self.history_days)
        totals = self.history.sum(axis=1)
        dow = self.features.loc[self.history_days, "dow"].to_numpy()
        regular = self.features.loc[self.history_days, "special"].to_numpy() == 0
        age = n_days - np.arange(n_days)  # 1 = последний день истории
        mon_thu = regular & (dow <= 3)

        anchor = np.median(totals[mon_thu & (age <= 7)], axis=0)
        reference = np.maximum(np.median(totals[mon_thu & (age <= 42)], axis=0), 1)
        typical_day = np.zeros((7, 24, len(self.routes)))
        for d in range(7):
            level = anchor * np.median(totals[regular & (dow == d) & (age <= 42)], axis=0) / reference
            shape_days = (mon_thu if d <= 3 else regular & (dow == d)) & (age <= 28)
            hours = self.history[shape_days].sum(axis=0)
            typical_day[d] = hours / np.maximum(hours.sum(axis=0), 1) * level

        profile = np.zeros((len(days), 24, len(self.routes)))
        for i, day in enumerate(days):
            if self.features.at[day, "holiday"]:
                profile[i] = typical_day[6]
            elif self.features.at[day, "work_weekend"]:
                profile[i] = (typical_day[4] + typical_day[5]) / 2
            else:
                profile[i] = typical_day[day.dayofweek]
        return profile

    def _spread_over_hours(self, profile, day_totals, days) -> np.ndarray:
        """Раскладывает суточные суммы по часам формой профиля. В праздники, рабочие выходные и дни, когда маршрут
        по профилю не ходит (< 5% прогноза, напр. маршрут 50 в выходные), остаётся сумма профиля."""
        profile_totals = profile.sum(axis=1)
        totals = np.clip(day_totals, 0, None)
        special = self.features.loc[days, "special"].to_numpy() == 1
        keep_profile = special[:, None] | (profile_totals < 0.05 * np.maximum(totals, 1))
        totals = np.where(keep_profile, profile_totals, totals)
        return profile / np.maximum(profile_totals[:, None, :], 1e-9) * totals[:, None, :]

    def _new_year_factor(self) -> float:
        """Уровень первых рабочих дней после новогодних праздников (9–10 января) к тем же дням недели трёх
        следующих недель, ≈ 0.90."""
        daily = pd.Series(self.history.sum(axis=(1, 2)), index=self.history_days)
        work_days = [day for day in daily.loc["2025-01"].index
                     if self.features.at[day, "day_off"] == 0 and day.dayofweek < 5]
        ratios = [daily[day] / daily[[day + pd.Timedelta(weeks=k) for k in (1, 2, 3)]].median()
                  for day in work_days[:2]]
        return float(np.mean(ratios))


def main():
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else DATASET_PATH
    hourly, template = load_dataset(dataset_path)
    features = build_day_features(load_external_data(CACHE_DIR))

    forecast = TramForecaster(hourly, features).predict(FORECAST_DAYS)

    # ответ в сетке организаторов; у маршрута 5 в данных нет посадок -> 0
    routes = list(hourly.columns)
    predicted = pd.DataFrame(
        [(route, day.strftime("%Y-%m-%d"), hour, forecast[i, hour, r])
         for i, day in enumerate(FORECAST_DAYS) for hour in range(24) for r, route in enumerate(routes)],
        columns=["route", "date", "hour", "prediction"])
    submission = template.merge(predicted, on=["route", "date", "hour"], how="left")
    submission["prediction"] = submission["prediction"].fillna(0).clip(lower=0).round().astype(int)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(OUTPUT_PATH, sep=";", index=False)
    print(f"{OUTPUT_PATH}: {len(submission)} строк, всего посадок {submission['prediction'].sum():,}")


if __name__ == "__main__":
    main()
