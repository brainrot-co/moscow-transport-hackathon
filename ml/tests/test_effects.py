import numpy as np
import pandas as pd

from mtml.worker.effects import compute_effects, neutralize

START, END = pd.Timestamp("2025-11-01"), pd.Timestamp("2025-11-07")


def calendar_covariates():
    ts = pd.date_range("2025-10-25", "2025-11-07 23:00", freq="h")
    day = ts.normalize()
    holidays = day.isin(pd.to_datetime(["2025-11-03", "2025-11-04"]))
    working_saturday = day == pd.Timestamp("2025-11-01")
    # как в производственном календаре: 2–4 ноября — один праздничный блок
    block = day.isin(pd.to_datetime(["2025-11-02", "2025-11-03", "2025-11-04"]))
    return pd.DataFrame(
        {
            "route": 17,
            "ts": ts,
            "is_non_working": (((ts.dayofweek >= 5) & ~working_saturday) | holidays).astype(int),
            "is_holiday_weekday": holidays.astype(int),
            "is_shortened": working_saturday.astype(int),
            "day_type": np.select(
                [block, working_saturday, ts.dayofweek == 5, ts.dayofweek == 6],
                ["holiday", "pre_holiday", "saturday", "sunday"],
                "workday",
            ),
            "school_holiday_modular": ((day >= "2025-10-25") & (day <= "2025-11-02")).astype(int),
            "school_holiday_quarter": 0,
        }
    )


class CalendarModel:
    """Прогноз посадок по формуле: в праздник вдвое меньше, в каникулы на 10% меньше."""

    future_covariates = ("is_holiday_weekday", "day_type", "school_holiday_modular")

    def __init__(self, covariates: pd.DataFrame):
        self.covariates = covariates

    def predict(self, start: pd.Timestamp, end: pd.Timestamp):
        rows = self.covariates[self.covariates["ts"].between(start, end + pd.Timedelta(hours=23))]
        factor = (1 - 0.5 * rows["is_holiday_weekday"]) * (1 - 0.1 * rows["school_holiday_modular"])
        return pd.DataFrame({"route": rows["route"], "ts": rows["ts"], "yhat": 1000 * factor})


def test_neutral_holiday_becomes_ordinary_day_only_on_horizon():
    covariates = calendar_covariates()
    neutral = neutralize(covariates, "holiday", START, END).set_index("ts")

    assert neutral.loc["2025-11-04 08:00", "day_type"] == "workday"
    assert neutral.loc["2025-11-04 08:00", "is_non_working"] == 0
    assert neutral.loc["2025-11-01 08:00", "day_type"] == "saturday"
    assert neutral.loc["2025-11-01 08:00", "is_non_working"] == 1
    assert neutral.loc["2025-10-26 08:00", "is_non_working"] == 1
    assert (
        neutral["school_holiday_modular"] == covariates.set_index("ts")["school_holiday_modular"]
    ).all()


def test_effects_match_model_formula_and_only_changed_days():
    model = CalendarModel(calendar_covariates())
    forecasts = model.predict(START, END)
    effects = compute_effects(model, forecasts, START, END).set_index(["factor", "date"])

    holiday = effects.loc["holiday"]
    assert set(holiday.index) == set(
        pd.to_datetime(["2025-11-01", "2025-11-02", "2025-11-03", "2025-11-04"])
    )
    assert np.isclose(holiday.loc["2025-11-03", "log_effect"], np.log1p(12000) - np.log1p(24000))
    assert np.isclose(holiday.loc["2025-11-01", "log_effect"], 0)
    school = effects.loc["school_holiday"]
    assert set(school.index) == set(pd.to_datetime(["2025-11-01", "2025-11-02"]))
    assert np.isclose(school.loc["2025-11-02", "yhat_without"], 24000)
    assert model.covariates.equals(calendar_covariates())


def test_model_without_covariates_has_no_effects():
    class Naive:
        pass

    forecasts = pd.DataFrame({"route": [17], "ts": [START], "yhat": [1.0]})
    assert compute_effects(Naive(), forecasts, START, END).empty
