import time
from dataclasses import dataclass

import pandas as pd

from mtml.data import ROOT
from mtml.forecasters.base import Forecaster
from mtml.metrics import evaluate

RUNS_DIR = ROOT / "ml" / "artifacts" / "runs"

# прокси для ноября–декабря: тот же горизонт 61 день
PROXY_CUTOFF = "2025-09-01"
PROXY_END = "2025-10-31"


@dataclass
class BacktestResult:
    forecaster: Forecaster
    cutoff: str
    end: str
    history: pd.DataFrame
    truth: pd.DataFrame
    preds: pd.DataFrame
    metrics: dict
    seconds: float


def backtest(
    forecaster: Forecaster,
    series: pd.DataFrame,
    cutoff: str = PROXY_CUTOFF,
    end: str = PROXY_END,
):
    """Контекст — всё до cutoff, прогноз и оценка — на [cutoff, end]."""
    cutoff_ts = pd.Timestamp(cutoff)
    history = series[series["ts"] < cutoff_ts]
    truth = series[
        (series["ts"] >= cutoff_ts) & (series["ts"] < pd.Timestamp(end) + pd.Timedelta(days=1))
    ]
    started = time.perf_counter()
    preds = forecaster.fit(history).predict(cutoff, end)
    seconds = time.perf_counter() - started
    return BacktestResult(
        forecaster, cutoff, end, history, truth, preds, evaluate(preds, truth), seconds
    )
