import json
from pathlib import Path

import numpy as np
import pandas as pd

from mtml.storage import Volume
from mtml.worker.settings import WorkerSettings
from mtml.worker.year import calendar_days, fit_route, hourly_profile, predict_route, run_year

HISTORY = ("2025-01-01", "2025-10-31")


def synthetic_daily():
    """Январь–октябрь: базовый день 10 000, в июле вдвое меньше, в воскресенье на 40% меньше."""
    days = calendar_days(pd.Timestamp(HISTORY[0]), pd.Timestamp("2026-10-31"))
    days = days[days["date"] <= HISTORY[1]].copy()
    july = np.where(days["month"] == 7, 0.5, 1.0)
    sunday = np.where(days["day_type"] == "sunday", 0.6, 1.0)
    days["y"] = 10_000 * july * sunday
    return days


def test_month_and_day_type_effects_are_recovered():
    daily = synthetic_daily()
    model = fit_route(daily)
    future = calendar_days(pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-31"))
    future = future[future["date"].between("2026-07-01", "2026-07-31")]
    pred = predict_route(model, future).set_index("date")

    assert np.isclose(pred.loc["2026-07-01", "yhat"], 5_000, rtol=0.01)
    assert np.isclose(pred.loc["2026-07-05", "yhat"], 3_000, rtol=0.01)


def test_unseen_month_takes_last_observed_month():
    model = fit_route(synthetic_daily())
    future = calendar_days(pd.Timestamp("2025-11-01"), pd.Timestamp("2025-11-30"))
    future = future[future["date"] >= "2025-11-01"]
    pred = predict_route(model, future).set_index("date")

    assert np.isclose(pred.loc["2025-11-05", "yhat"], 10_000, rtol=0.01)


def test_hourly_profile_shares_sum_to_one_per_kind():
    ts = pd.date_range("2025-10-01", "2025-10-31 23:00", freq="h")
    series = pd.DataFrame({"route": 25, "ts": ts, "y": np.where(ts.hour == 8, 100.0, 1.0)})
    series["date"] = series["ts"].dt.normalize()
    profile = hourly_profile(series, calendar_days(ts.min(), ts.max()))

    assert np.allclose(profile.groupby(level="kind").sum(), 1)
    assert profile.loc[("workday", 8)] > profile.loc[("workday", 3)]


def write_volume(volume: Volume):
    ts = pd.date_range(HISTORY[0], f"{HISTORY[1]} 23:00", freq="h")
    boardings = np.where((ts.hour >= 6) & (ts.hour <= 23), 500, 0)
    actuals = pd.DataFrame({"route": np.int16(25), "ts": ts, "boardings": boardings})
    volume.actuals.parent.mkdir(parents=True)
    actuals.to_parquet(volume.actuals, index=False)
    dates = pd.date_range(*HISTORY)
    status = pd.DataFrame(
        {"route": np.int16(25), "date": dates, "status": "final", "anomaly": False}
    )
    status.to_parquet(volume.day_status, index=False)
    volume.watermark.parent.mkdir(parents=True)
    volume.watermark.write_text(json.dumps({"watermark": HISTORY[1]}))


def test_year_run_publishes_hourly_year_with_cold_start(tmp_path: Path):
    volume = Volume(tmp_path)
    write_volume(volume)
    run_id = run_year(volume, WorkerSettings(routes=(5, 25)), pd.Timestamp("2025-11-01 03:00"))

    forecasts = pd.read_parquet(volume.runs / run_id / "forecasts.parquet")
    meta = json.loads((volume.runs / run_id / "meta.json").read_text())
    assert len(forecasts) == 2 * 365 * 24
    assert (forecasts.loc[forecasts["route"] == 5, "yhat"] == 0).all()
    assert meta["model"]["months_without_history"] == [11, 12]
    assert json.loads(volume.active.read_text())["year"] == run_id
