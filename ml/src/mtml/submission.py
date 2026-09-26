from pathlib import Path

import pandas as pd

from mtml.data import ALL_ROUTES
from mtml.forecasters.base import horizon_hours

SUBMISSION_START = "2025-11-01"
SUBMISSION_END = "2025-12-31"


def to_submission(
    preds: pd.DataFrame,
    start: str = SUBMISSION_START,
    end: str = SUBMISSION_END,
):
    """Маршруты без прогноза (маршрут 5) получают 0; прогноз обрезается в ≥ 0 и округляется."""
    index = pd.MultiIndex.from_product(
        [ALL_ROUTES, horizon_hours(start, end)], names=["route", "ts"]
    )
    yhat = preds.set_index(["route", "ts"])["yhat"]
    if not yhat.index.isin(index).all():
        raise ValueError("В прогнозе есть точки вне сетки сабмишена")
    full = yhat.reindex(index).fillna(0.0).clip(lower=0).round().astype(int).reset_index()
    sub = pd.DataFrame(
        {
            "route": full["route"],
            "date": full["ts"].dt.strftime("%Y-%m-%d"),
            "hour": full["ts"].dt.hour,
            "prediction": full["yhat"],
        }
    )
    expected = len(ALL_ROUTES) * len(horizon_hours(start, end))
    if len(sub) != expected:
        raise ValueError(f"В сабмишене {len(sub)} строк вместо {expected}")
    return sub


def write_submission(sub: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(path, sep=";", index=False)
