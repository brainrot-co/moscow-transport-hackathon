import json
from pathlib import Path

import pandas as pd
import pytest

from mtml.storage import Volume
from mtml.worker.publish import publish_calendar, publish_run
from mtml.worker.quality import QualityError, check_forecast

START, END = pd.Timestamp("2025-11-01"), pd.Timestamp("2025-11-14")


def weekly_pattern(start: str, days: int, weekday: float, weekend: float, column: str):
    ts = pd.date_range(start, periods=days * 24, freq="h")
    value = [weekday if t.dayofweek < 5 else weekend for t in ts]
    return pd.DataFrame({"route": 50, "ts": ts, column: [v / 24 for v in value]})


def test_route_closed_on_weekends_passes():
    history = weekly_pattern("2025-10-04", 28, 24000, 50, "y")
    forecasts = weekly_pattern("2025-11-01", 14, 23000, 100, "yhat")

    assert check_forecast(forecasts, history, (50,), START, END)["weekly_totals"] == "ok"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda f: f.assign(yhat=f["yhat"] * 10), "недельные суммы"),
        (lambda f: f.assign(yhat=-f["yhat"]), "отрицательные"),
        (lambda f: f.iloc[:-5], "сетка"),
    ],
)
def test_broken_forecast_is_rejected(change: object, message: str):
    history = weekly_pattern("2025-10-04", 28, 24000, 8000, "y")
    forecasts = change(weekly_pattern("2025-11-01", 14, 24000, 8000, "yhat"))

    with pytest.raises(QualityError, match=message):
        check_forecast(forecasts, history, (50,), START, END)


def publish(volume: Volume, run_id: str, keep_runs: int = 2):
    forecasts = pd.DataFrame({"route": [1], "ts": [START], "yhat": [1.0]})
    meta = {"kind": "short", "created_at": run_id[6:21]}
    publish_run(volume, run_id, {"forecasts": forecasts}, meta, keep_runs)


def test_publish_switches_pointer_and_prunes_old_runs(tmp_path: Path):
    volume = Volume(tmp_path)
    for day in (1, 2, 3):
        publish(volume, f"short-2025110{day}T030000-m")

    active = json.loads(volume.active.read_text())
    assert active["short"] == "short-20251103T030000-m"
    assert sorted(p.name for p in volume.runs.iterdir()) == [
        "short-20251102T030000-m",
        "short-20251103T030000-m",
    ]


def test_failed_publish_leaves_no_staging_and_keeps_pointer(tmp_path: Path):
    volume = Volume(tmp_path)
    publish(volume, "short-20251101T030000-a")
    broken = {"forecasts": pd.DataFrame({"route": [1]}), "bad": object()}

    with pytest.raises(AttributeError):
        publish_run(volume, "short-20251102T030000-b", broken, {"kind": "short"}, 2)
    assert json.loads(volume.active.read_text())["short"] == "short-20251101T030000-a"
    assert [p.name for p in volume.runs.iterdir()] == ["short-20251101T030000-a"]


def test_calendar_marks_november_holidays(tmp_path: Path):
    volume = Volume(tmp_path)
    publish_calendar(volume)

    calendar = pd.read_parquet(volume.calendar).set_index("date")["day_type"]
    assert calendar[pd.Timestamp("2025-11-04")] == "holiday"
    assert calendar[pd.Timestamp("2025-11-05")] == "post_holiday"
    assert calendar[pd.Timestamp("2025-11-08")] == "saturday"
