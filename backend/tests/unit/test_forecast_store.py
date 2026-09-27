import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from app.ml.models import (
    ActualRecord,
    ForecastRecord,
    ForecastSnapshot,
    RunMetadata,
    SnapshotError,
)


def metadata(kind: str, cutoff: date = date(2026, 9, 30)) -> RunMetadata:
    return RunMetadata(
        run_id=f"{kind}-1",
        kind=kind,
        schema_version=1,
        data_cutoff=cutoff,
        step="hour",
        routes=frozenset({7}),
    )


def test_actual_uses_value_and_never_forecast_fields():
    timestamp = datetime(2026, 10, 1, 10)
    snapshot = ForecastSnapshot(
        actuals={(7, timestamp): ActualRecord(7, timestamp, 120)},
        short={(7, timestamp): ForecastRecord(7, timestamp, 200)},
        year={},
        short_meta=metadata("short"),
        year_meta=metadata("year"),
        watermark=date(2026, 10, 1),
    )

    row = snapshot.resolve(7, timestamp)

    assert row.as_dict() == {
        "route": 7,
        "ts": "2026-10-01T10:00:00",
        "source": "actual",
        "value": 120,
        "yhat_model": None,
        "yhat": None,
        "q10": None,
        "q90": None,
        "estimated": False,
        "applied": [],
    }


def test_short_wins_when_short_and_year_have_same_timestamp():
    timestamp = datetime(2026, 10, 2, 10)
    snapshot = ForecastSnapshot(
        actuals={},
        short={(7, timestamp): ForecastRecord(7, timestamp, 210)},
        year={(7, timestamp): ForecastRecord(7, timestamp, 170)},
        short_meta=metadata("short"),
        year_meta=metadata("year"),
    )

    row = snapshot.resolve(7, timestamp)

    assert row.source == "forecast"
    assert row.yhat_model == 210


def test_missing_forecast_is_not_returned_as_zero():
    timestamp = datetime(2026, 10, 2, 10)
    snapshot = ForecastSnapshot(actuals={}, short={}, year={})

    row = snapshot.resolve(7, timestamp)

    assert row.source is None
    assert row.yhat is None
    assert row.availability == "unavailable"


def test_cold_start_forecast_is_not_returned_as_zero():
    timestamp = datetime(2026, 10, 2, 10)
    short_meta = replace(
        metadata("short"),
        routes=frozenset({5}),
        cold_start_routes=frozenset({5}),
    )
    year_meta = replace(
        metadata("year"),
        routes=frozenset({5}),
        cold_start_routes=frozenset({5}),
    )
    snapshot = ForecastSnapshot(
        actuals={},
        short={(5, timestamp): ForecastRecord(5, timestamp, 0)},
        year={(5, timestamp): ForecastRecord(5, timestamp, 0)},
        short_meta=short_meta,
        year_meta=year_meta,
    )

    row = snapshot.resolve(5, timestamp)

    assert row.source is None
    assert row.yhat is None
    assert row.availability == "cold_start"


def test_incompatible_runs_are_rejected():
    with pytest.raises(SnapshotError, match="incompatible"):
        ForecastSnapshot(
            actuals={},
            short={},
            year={},
            short_meta=metadata("short"),
            year_meta=metadata("year", cutoff=date(2026, 9, 29)),
        )


def test_store_loads_published_parquet_snapshot(tmp_path: Path):
    import pyarrow as pa
    import pyarrow.parquet as parquet

    (tmp_path / "runs" / "short-1").mkdir(parents=True)
    (tmp_path / "runs" / "year-1").mkdir(parents=True)
    (tmp_path / "actuals").mkdir()
    (tmp_path / "state").mkdir()
    (tmp_path / "active.json").write_text(
        json.dumps({"schema_version": 1, "short": "short-1", "year": "year-1"}),
        encoding="utf-8",
    )
    for kind, run_id in (("short", "short-1"), ("year", "year-1")):
        (tmp_path / "runs" / run_id / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "kind": kind,
                    "schema_version": 1,
                    "data_cutoff": "2026-09-30",
                    "horizon": {"step": "hour"},
                    "routes": [7],
                }
            ),
            encoding="utf-8",
        )
        parquet.write_table(
            pa.table(
                {
                    "route": [7],
                    "ts": ["2026-10-01T10:00:00"],
                    "yhat": [200.0 if kind == "short" else 180.0],
                    "q10": [100.0],
                    "q90": [300.0],
                }
            ),
            tmp_path / "runs" / run_id / "forecasts.parquet",
        )
    parquet.write_table(
        pa.table(
            {
                "route": [7],
                "ts": ["2026-10-01T10:00:00"],
                "boardings": [120],
                "status": ["final"],
            }
        ),
        tmp_path / "actuals" / "actuals_hourly.parquet",
    )
    (tmp_path / "state" / "watermark.json").write_text(
        json.dumps({"watermark": "2026-10-01"}),
        encoding="utf-8",
    )

    from app.ml.store import ForecastStore

    snapshot = ForecastStore(tmp_path)._load_from_disk()

    assert snapshot.resolve(7, datetime(2026, 10, 1, 10)).value == 120


def partial_day_snapshot() -> ForecastSnapshot:
    hours = [datetime(2026, 10, 2, hour) for hour in range(24)]
    return ForecastSnapshot(
        # в демо данные за сегодня лежат на все 24 часа, день ещё partial
        actuals={(7, ts): ActualRecord(7, ts, 100, status="partial") for ts in hours},
        short={(7, ts): ForecastRecord(7, ts, 150) for ts in hours},
        year={},
        short_meta=metadata("short", date(2026, 10, 1)),
        year_meta=metadata("year", date(2026, 10, 1)),
        watermark=date(2026, 10, 1),
    )


def test_passed_hour_of_partial_day_is_estimated_actual():
    now = datetime(2026, 10, 2, 15, 25)
    snapshot = partial_day_snapshot()

    passed = snapshot.resolve(7, datetime(2026, 10, 2, 14), now)
    current = snapshot.resolve(7, datetime(2026, 10, 2, 15), now)

    assert (passed.source, passed.value, passed.estimated) == ("actual", 100, True)
    assert (current.source, current.yhat) == ("forecast", 150)


def test_without_now_partial_day_stays_forecast():
    row = partial_day_snapshot().resolve(7, datetime(2026, 10, 2, 8))

    assert row.source == "forecast"
