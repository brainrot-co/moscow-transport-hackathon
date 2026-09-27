import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from mtml.ingest.actuals import update_actuals
from mtml.ingest.raw import copy_query, merge_raw
from mtml.ingest.reader import ReadStats, load_batch
from mtml.ingest.settings import IngestSettings
from mtml.ingest.status import day_status, watermark
from mtml.storage import Volume, write_atomic, write_json_atomic

log = logging.getLogger(__name__)

# TODO: не дописал комменты


@dataclass
class BatchRecord:
    batch_id: str
    file_name: str
    sha256: str
    received_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    rows_total: int = 0
    rows_refused: int = 0
    rows_quarantined: int = 0
    rows_unknown_route: int = 0
    rows_valid: int = 0
    rows_new: int = 0
    date_min: date | None = None
    date_max: date | None = None
    error: str | None = None


def file_sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_journal(volume: Volume):
    """Возвращает журнал загрузок, если его нет, то пустой фрейм"""
    if not volume.batches.exists():
        return pd.DataFrame(columns=list(BatchRecord.__dataclass_fields__))
    return pd.read_parquet(volume.batches)


def append_journal(volume: Volume, record: BatchRecord):
    journal = pd.concat([read_journal(volume), pd.DataFrame([asdict(record)])], ignore_index=True)
    write_atomic(volume.batches, lambda tmp: journal.to_parquet(tmp, index=False))


def refresh_status(volume: Volume, settings: IngestSettings, now: datetime):
    """Статусы зависят от возраста дня, поэтому пересчитываются и без новых данных."""
    if not volume.actuals.exists():
        return None
    actuals = pd.read_parquet(volume.actuals)
    status = day_status(actuals, now.date(), settings)
    write_atomic(volume.day_status, lambda tmp: status.to_parquet(tmp, index=False))
    mark = watermark(status)
    previous = None
    if volume.watermark.exists():
        previous = json.loads(volume.watermark.read_text(encoding="utf-8"))["watermark"]
    # статусы пересчитываются каждый опрос, в лог — только сдвиг знака
    if str(mark) != str(previous):
        log.info("Водяной знак %s → %s (сейчас %s)", previous, mark, now)
    write_json_atomic(
        volume.watermark,
        {
            "watermark": mark,
            "latest_data": actuals.loc[actuals["boardings"] > 0, "ts"].max(),
            "updated_at": now,
        },
    )
    return mark


def ingest_file(path: Path, volume: Volume, settings: IngestSettings, now: datetime):
    """Основной цикл загрузки одного файла: проверка, чтение, запись сырых данных, обновление фактических посадок и статусов."""

    # Собираем объект BatchRecode, batch_id должен быть уникальным.
    record = BatchRecord(
        batch_id=f"{now:%Y%m%dT%H%M%S}-{uuid4().hex[:8]}",
        file_name=path.name,
        sha256=file_sha256(path),
        received_at=now,
    )

    journal = read_journal(volume)
    loaded = journal.loc[journal["status"] == "ok", "sha256"]
    if record.sha256 in set(loaded):
        record.status, record.finished_at = "duplicate", now
        append_journal(volume, record)
        log.info("%s уже загружен ранее, пропускаю", path.name)
        return record

    volume.spill.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    con.execute(f"SET memory_limit = '{settings.memory_limit}'")
    con.execute(f"SET temp_directory = '{volume.spill}'")
    try:
        stats: ReadStats = load_batch(con, path, now, settings)
        for field, value in asdict(stats).items():
            setattr(record, field, value)
        if stats.rows_quarantined:
            query = "SELECT * FROM checked WHERE reason IS NOT NULL"
            target = volume.quarantine / f"{record.batch_id}.parquet"
            write_atomic(target, partial(copy_query, con, query))
        days, record.rows_new = merge_raw(con, volume.raw, record.batch_id)
        if days:
            record.date_min, record.date_max = days[0], days[-1]
            update_actuals(con, volume.raw, volume.actuals, days, record.batch_id, now)
        refresh_status(volume, settings, now)
        record.status = "ok"
    except (duckdb.Error, ValueError, OSError) as error:
        record.status, record.error = "failed", str(error)
        log.error("Не удалось загрузить %s: %s", path.name, error)
    finally:
        con.close()
        # время в журнале — по часам системы, длительность — реальная
        record.finished_at = now + timedelta(seconds=round(time.perf_counter() - started))
        append_journal(volume, record)
    if record.rows_unknown_route:
        log.warning(
            "%s: %d посадок на маршрутах не из справочника", path.name, record.rows_unknown_route
        )
    log.info(
        "%s: %s, строк %d, посадок %d (новых %d), отказов %d, в карантине %d, дни %s–%s",
        path.name,
        record.status,
        record.rows_total,
        record.rows_valid,
        record.rows_new,
        record.rows_refused,
        record.rows_quarantined,
        record.date_min,
        record.date_max,
    )
    return record


def process_inbox(volume: Volume, settings: IngestSettings, now: datetime):
    """Готовые файлы — только *.csv: писатель кладёт файл под другим именем и переименовывает."""
    for path in sorted(volume.inbox.glob("*.csv"), key=lambda p: p.stat().st_mtime):
        record = ingest_file(path, volume, settings, now)
        if record.status == "failed":
            volume.failed.mkdir(parents=True, exist_ok=True)
            (volume.failed / f"{path.name}.error.txt").write_text(record.error, encoding="utf-8")
            path.rename(volume.failed / path.name)
        else:
            volume.processed.mkdir(parents=True, exist_ok=True)
            path.rename(volume.processed / f"{record.batch_id}__{path.name}")
    refresh_status(volume, settings, now)
