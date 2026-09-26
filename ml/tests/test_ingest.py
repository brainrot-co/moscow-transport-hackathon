from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from mtml.ingest.pipeline import ingest_file, process_inbox
from mtml.ingest.reader import COLUMNS
from mtml.ingest.settings import IngestSettings
from mtml.ingest.status import day_status, watermark
from mtml.storage import Volume

NOW = datetime(2025, 9, 10, 12, 0)
SETTINGS = IngestSettings()


def row(
    tran_no: int,
    ts: str,
    route: str = "25 трамвай",
    result: int = 1,
    device: int = 1001,
):
    values = {
        "tran_no": tran_no,
        "device_no": device,
        "tran_date_time": ts,
        "begin_date_time": ts,
        "input_date_time": ts,
        "crd_hashcode": "abc",
        "validation_result": result,
        "tran_type_id": 52,
        "place_id": 39707,
        "good_type": "30 дней",
        "pass_route": "НГПТ",
        "ngpt_route": route,
        "bus_exit_no": 205,
        "garage_number": 31117,
    }
    return ";".join(str(values[c]) for c in COLUMNS)


def write_csv(path: Path, rows: list[str]):
    # как у организаторов: заголовок с \n, строки данных с \r\n
    path.write_bytes((";".join(COLUMNS) + "\n" + "\r\n".join(rows) + "\r\n").encode())
    return path


def hourly(volume: Volume, route: int, ts: str):
    actuals = pd.read_parquet(volume.actuals)
    match = actuals[(actuals["route"] == route) & (actuals["ts"] == pd.Timestamp(ts))]
    return int(match["boardings"].sum())


@pytest.fixture
def volume(tmp_path: Path):
    return Volume(tmp_path / "data")


def test_refusals_and_quarantine_are_counted_not_loaded(volume: Volume, tmp_path: Path):
    path = write_csv(
        tmp_path / "batch.csv",
        [
            row(1, "2025-09-01 08:01:00"),
            row(2, "2025-09-01 08:02:00"),
            row(3, "2025-09-01 08:03:00"),
            row(4, "2025-09-01 08:04:00", result=90),
            row(5, "2025-13-45 08:00:00"),
            row(6, "2026-01-01 08:00:00"),
            row(7, "2019-01-01 08:00:00"),
            row(8, "2025-09-01 08:05:00", route=""),
            row(9, "2025-09-01 08:06:00", route="33 трамвай"),
        ],
    )
    record = ingest_file(path, volume, SETTINGS, NOW)

    assert record.status == "ok"
    assert (record.rows_total, record.rows_refused, record.rows_quarantined) == (9, 1, 4)
    assert (record.rows_valid, record.rows_unknown_route) == (4, 1)
    assert hourly(volume, 25, "2025-09-01 08:00") == 3
    quarantine = pd.read_parquet(volume.quarantine / f"{record.batch_id}.parquet")
    assert sorted(quarantine["reason"]) == ["bad_value", "future", "no_route", "too_old"]


def test_same_file_twice_is_skipped(volume: Volume, tmp_path: Path):
    path = write_csv(tmp_path / "batch.csv", [row(1, "2025-09-01 08:01:00")])
    ingest_file(path, volume, SETTINGS, NOW)
    second = ingest_file(path, volume, SETTINGS, NOW)

    assert second.status == "duplicate"
    assert hourly(volume, 25, "2025-09-01 08:00") == 1


def test_overlapping_files_are_not_double_counted(volume: Volume, tmp_path: Path):
    first = write_csv(
        tmp_path / "a.csv", [row(1, "2025-09-01 08:01:00"), row(2, "2025-09-01 08:02:00")]
    )
    second = write_csv(
        tmp_path / "b.csv", [row(2, "2025-09-01 08:02:00"), row(3, "2025-09-01 08:03:00")]
    )
    ingest_file(first, volume, SETTINGS, NOW)
    record = ingest_file(second, volume, SETTINGS, NOW)

    assert (record.rows_valid, record.rows_new) == (2, 1)
    assert hourly(volume, 25, "2025-09-01 08:00") == 3


def test_night_tail_from_previous_file_is_stitched(volume: Volume, tmp_path: Path):
    august = write_csv(
        tmp_path / "august.csv",
        [
            row(1, "2025-08-31 23:10:00"),
            row(2, "2025-09-01 00:20:00"),
            row(3, "2025-09-01 00:30:00"),
        ],
    )
    september = write_csv(
        tmp_path / "september.csv",
        [row(4, "2025-09-01 00:40:00"), row(5, "2025-09-01 08:00:00")],
    )
    ingest_file(august, volume, SETTINGS, NOW)
    ingest_file(september, volume, SETTINGS, NOW)

    assert hourly(volume, 25, "2025-09-01 00:00") == 3
    assert hourly(volume, 25, "2025-09-01 08:00") == 1


def test_hours_without_boardings_are_zero_inside_loaded_day(volume: Volume, tmp_path: Path):
    ingest_file(
        write_csv(tmp_path / "b.csv", [row(1, "2025-09-01 08:01:00")]), volume, SETTINGS, NOW
    )
    actuals = pd.read_parquet(volume.actuals)
    day = actuals[(actuals["route"] == 25) & (actuals["ts"].dt.date == date(2025, 9, 1))]

    assert len(day) == 24
    assert day["boardings"].sum() == 1


def test_broken_file_goes_to_failed(volume: Volume):
    volume.inbox.mkdir(parents=True)
    (volume.inbox / "broken.csv").write_text("какой-то;другой;заголовок\n1;2;3\n")
    process_inbox(volume, SETTINGS, NOW)

    assert (volume.failed / "broken.csv").exists()
    assert "Неожиданный заголовок" in (volume.failed / "broken.csv.error.txt").read_text()


def daily_actuals(days: dict[str, int]):
    return pd.DataFrame(
        {
            "route": 25,
            "ts": pd.to_datetime(list(days)) + pd.Timedelta(hours=8),
            "boardings": list(days.values()),
        }
    )


def status_of(status: pd.DataFrame, day: str, route: int = 25):
    return status.set_index(["route", "date"]).loc[(route, pd.Timestamp(day))]


def test_status_rules():
    days = {f"2025-08-{d:02d}": 1000 for d in range(1, 32)}
    days |= {"2025-09-01": 1000, "2025-09-02": 1000, "2025-09-03": 100}
    days |= {"2025-09-06": 1000, "2025-09-07": 900, "2025-09-09": 990, "2025-09-10": 500}
    status = day_status(daily_actuals(days), date(2025, 9, 10), IngestSettings(routes=(25,)))

    assert status_of(status, "2025-09-02")["status"] == "final"
    assert status_of(status, "2025-09-03")["status"] == "final"
    assert status_of(status, "2025-09-03")["anomaly"]
    assert status_of(status, "2025-09-04")["status"] == "missing"
    assert status_of(status, "2025-09-07")["status"] == "final"
    assert status_of(status, "2025-09-08")["status"] == "partial"
    assert status_of(status, "2025-09-09")["status"] == "final"
    assert status_of(status, "2025-09-10")["status"] == "partial"
    assert watermark(status) == date(2025, 9, 7)


def test_underfilled_recent_day_waits_for_uploads():
    days = {f"2025-08-{d:02d}": 1000 for d in range(1, 32)}
    days |= {f"2025-09-{d:02d}": 1000 for d in range(1, 9)} | {"2025-09-09": 700}
    status = day_status(daily_actuals(days), date(2025, 9, 10), IngestSettings(routes=(25,)))

    assert status_of(status, "2025-09-09")["status"] == "partial"
    assert not status_of(status, "2025-09-09")["anomaly"]
    assert watermark(status) == date(2025, 9, 8)


def test_route_without_history_does_not_hold_watermark():
    days = {f"2025-08-{d:02d}": 1000 for d in range(1, 32)}
    days |= {f"2025-09-{d:02d}": 1000 for d in range(1, 10)}
    status = day_status(daily_actuals(days), date(2025, 9, 10), IngestSettings(routes=(5, 25)))

    assert status_of(status, "2025-09-09", route=5)["status"] == "missing"
    assert watermark(status) == date(2025, 9, 9)
