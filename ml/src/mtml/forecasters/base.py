from typing import Protocol

import pandas as pd


class Forecaster(Protocol):
    """fit: [route, ts, y] на плотной сетке; predict: [route, ts, yhat, q*], end включительно."""

    name: str

    def fit(self, history: pd.DataFrame): ...

    def predict(self, start: str | pd.Timestamp, end: str | pd.Timestamp): ...


def horizon_hours(start: str | pd.Timestamp, end: str | pd.Timestamp):
    return pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")


def check_contiguous(history: pd.DataFrame, start: str | pd.Timestamp):
    last = history["ts"].max()
    if last + pd.Timedelta(hours=1) != pd.Timestamp(start):
        raise ValueError(f"История кончается {last}, а прогноз начинается {start}")
