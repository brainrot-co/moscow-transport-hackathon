import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mtml.storage import Volume
from mtml.worker import schedule
from mtml.worker.context import Context
from mtml.worker.monitor import evaluate_run
from mtml.worker.quality import QualityError
from mtml.worker.schedule import WorkerState, load_state, rerun_reason, tick
from mtml.worker.settings import WorkerSettings

SETTINGS = WorkerSettings(min_rerun_minutes=10)
REAL = datetime(2026, 9, 27, 12, 0)
VIRTUAL = datetime(2025, 11, 1, 12, 0)
MARK = date(2025, 10, 31)


def ran_at(watermark: date, real: datetime = REAL, virtual: datetime = VIRTUAL):
    return WorkerState(last_run_real=real, last_run_virtual=virtual, last_watermark=watermark)


@pytest.mark.parametrize(
    ("state", "watermark", "virtual", "real", "expected"),
    [
        (WorkerState(), None, VIRTUAL, REAL, None),
        (WorkerState(), MARK, VIRTUAL, REAL, "первый прогон"),
        (ran_at(MARK), MARK, VIRTUAL, REAL + timedelta(hours=1), None),
        (ran_at(date(2025, 10, 30)), MARK, VIRTUAL, REAL + timedelta(minutes=5), None),
        (ran_at(date(2025, 10, 30)), MARK, VIRTUAL, REAL + timedelta(minutes=11), "водяной знак"),
        (
            ran_at(MARK),
            MARK,
            datetime(2025, 11, 2, 3, 5),
            REAL + timedelta(minutes=11),
            "ночной прогон",
        ),
        # и ночь, и сдвиг знака наступили, но с прошлого прогона меньше MIN_RERUN_MINUTES
        (
            ran_at(date(2025, 10, 30)),
            MARK,
            datetime(2025, 11, 2, 3, 5),
            REAL + timedelta(minutes=5),
            None,
        ),
        (
            ran_at(MARK, virtual=datetime(2025, 11, 2, 3, 1)),
            MARK,
            datetime(2025, 11, 2, 9),
            REAL,
            None,
        ),
    ],
)
def test_rerun_reason(
    state: WorkerState, watermark: date, virtual: datetime, real: datetime, expected: str | None
):
    reason = rerun_reason(state, watermark, virtual, real, SETTINGS)
    assert reason == expected or (expected and reason.startswith(expected))


def write_minimal_volume(volume: Volume):
    volume.watermark.parent.mkdir(parents=True)
    volume.watermark.write_text(json.dumps({"watermark": MARK.isoformat()}))
    volume.actuals.parent.mkdir(parents=True)
    ts = pd.date_range("2025-10-01", periods=24, freq="h")
    pd.DataFrame({"route": 1, "ts": ts, "boardings": 1}).to_parquet(volume.actuals)
    status = pd.DataFrame({"route": [1], "date": [pd.Timestamp("2025-10-01")], "status": "final"})
    status.to_parquet(volume.day_status)


def fake_context(volume: Volume, routes: tuple[int, ...]):
    mark = date.fromisoformat(json.loads(volume.watermark.read_text())["watermark"])
    return Context(pd.DataFrame(), mark, routes, ())


def fake_build(kind: str, cutoffs: list[date]):
    def build(_volume: Volume, context: Context, _settings: WorkerSettings, now: datetime):
        cutoffs.append(context.watermark)
        meta = {"kind": kind, "created_at": now, "data_cutoff": context.watermark}
        return f"{kind}-{now:%Y%m%dT%H%M%S}", {"forecasts": pd.DataFrame({"x": [1]})}, meta

    return build


def test_quality_error_keeps_service_running_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    volume = Volume(tmp_path)
    write_minimal_volume(volume)
    cutoffs = []

    def broken_short(*args: object):
        raise QualityError(f"недельные суммы от 0.1 до 5, прогон на {args[-1]}")

    monkeypatch.setattr(schedule, "build_context", fake_context)
    monkeypatch.setattr(schedule, "build_short", broken_short)
    monkeypatch.setattr(schedule, "build_year", fake_build("year", cutoffs))
    assert tick(volume, SETTINGS, VIRTUAL, REAL) == "первый прогон"

    state = load_state(volume)
    # годовой без короткого не публикуется: бэкенд не примет пару с разным data_cutoff
    assert cutoffs == []
    assert not volume.active.exists()
    assert state.last_watermark == MARK
    assert "недельные суммы" in state.last_error
    assert tick(volume, SETTINGS, VIRTUAL, REAL + timedelta(minutes=1)) is None


def test_pair_shares_watermark_even_if_ingest_moves_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    volume = Volume(tmp_path)
    write_minimal_volume(volume)
    cutoffs = []
    slow_short = fake_build("short", cutoffs)

    def short_while_ingest_runs(*args: object):
        result = slow_short(*args)
        # пока считается Chronos, ingest сдвигает водяной знак
        volume.watermark.write_text(json.dumps({"watermark": "2025-11-03"}))
        return result

    monkeypatch.setattr(schedule, "build_context", fake_context)
    monkeypatch.setattr(schedule, "build_short", short_while_ingest_runs)
    monkeypatch.setattr(schedule, "evaluate_runs", lambda *_: None)
    monkeypatch.setattr(schedule, "build_year", fake_build("year", cutoffs))
    tick(volume, SETTINGS, VIRTUAL, REAL)

    active = json.loads(volume.active.read_text())
    assert cutoffs == [MARK, MARK]
    assert active["short"] == "short-20251101T120000"
    assert active["year"] == "year-20251101T120000"
    assert load_state(volume).last_watermark == MARK


def test_accuracy_by_lead_ignores_cold_start_routes():
    ts = pd.date_range("2025-11-01", "2025-11-10 23:00", freq="h")
    run = pd.concat(
        [
            pd.DataFrame({"route": 17, "ts": ts, "yhat": 100.0}),
            pd.DataFrame({"route": 5, "ts": ts, "yhat": 0.0}),
        ]
    )
    facts = pd.DataFrame({"route": 17, "ts": ts, "y": np.where(ts.day == 1, 100.0, 125.0)})
    meta = {
        "run_id": "short-x",
        "kind": "short",
        "model": {"name": "m"},
        "data_cutoff": "2025-10-31",
        "cold_start_routes": [5],
    }
    rows = {row["lead"]: row for row in evaluate_run(run, meta, facts)}

    assert rows["1 день"]["wape_score"] == 1.0
    assert rows["2–7 дней"]["wape_score"] == pytest.approx(0.8)
    assert rows["8–30 дней"]["days"] == 3
    assert "31+ дней" not in rows
