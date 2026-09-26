import pandas as pd

from mtml.forecasters.base import check_contiguous, horizon_hours


class WeeklyProfile:
    def __init__(self, n_weeks: int = 4, agg: str = "median"):
        self.n_weeks = n_weeks
        self.agg = agg
        self.name = f"weekly_{agg}_{n_weeks}w"

    def fit(self, history: pd.DataFrame):
        self.history = history
        cutoff = history["ts"].max() - pd.Timedelta(weeks=self.n_weeks)
        recent = history[history["ts"] > cutoff]
        keys = [recent["route"], recent["ts"].dt.dayofweek, recent["ts"].dt.hour]
        self.profile = recent.groupby(keys)["y"].agg(self.agg).rename("yhat")
        self.profile.index.names = ["route", "dow", "hour"]
        return self

    def predict(self, start: str | pd.Timestamp, end: str | pd.Timestamp):
        check_contiguous(self.history, start)
        hours = horizon_hours(start, end)
        routes = self.history["route"].unique()
        out = pd.MultiIndex.from_product([routes, hours], names=["route", "ts"]).to_frame(
            index=False
        )
        out["dow"] = out["ts"].dt.dayofweek
        out["hour"] = out["ts"].dt.hour
        out = out.join(self.profile, on=["route", "dow", "hour"])
        return out[["route", "ts", "yhat"]]


class SeasonalNaive(WeeklyProfile):
    def __init__(self):
        super().__init__(n_weeks=1, agg="mean")
        self.name = "seasonal_naive_1w"
