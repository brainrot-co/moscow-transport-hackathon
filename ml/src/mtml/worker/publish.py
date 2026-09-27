import json
import logging
import os
import shutil

import pandas as pd

from mtml.covariates import EXTERNAL_DIR, load_calendar, load_day_features
from mtml.storage import Volume, write_atomic, write_json_atomic

SCHEMA_VERSION = 1
CORRECTION_FACTORS_PATH = EXTERNAL_DIR / "correction_factors.json"

log = logging.getLogger(__name__)


def write_run(
    volume: Volume, run_id: str, tables: dict[str, pd.DataFrame], meta: dict[str, object]
):
    """Прогон пишется во временную папку и переименовывается; в active.json он ещё не попадает."""
    staging = volume.runs / f"{run_id}.tmp"
    target = volume.runs / run_id
    if target.exists():
        raise FileExistsError(f"Прогон {run_id} уже опубликован")
    staging.mkdir(parents=True)
    try:
        for name, table in tables.items():
            table.to_parquet(staging / f"{name}.parquet", index=False)
        text = json.dumps(meta, ensure_ascii=False, indent=2, default=str)
        (staging / "meta.json").write_text(text, encoding="utf-8")
        os.replace(staging, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def activate(volume: Volume, runs: dict[str, str], published_at: object, keep_runs: int):
    """Одна запись active.json на все переданные прогоны: бэкенд не увидит пару с разным cutoff."""
    active = {"schema_version": SCHEMA_VERSION}
    if volume.active.exists():
        active = json.loads(volume.active.read_text(encoding="utf-8"))
    active.update(runs)
    active["published_at"] = published_at
    write_json_atomic(volume.active, active)
    for kind, run_id in runs.items():
        log.info("Опубликован прогон %s", run_id)
        prune_runs(volume, kind, keep_runs)


def publish_run(
    volume: Volume,
    run_id: str,
    tables: dict[str, pd.DataFrame],
    meta: dict[str, object],
    keep_runs: int,
):
    write_run(volume, run_id, tables, meta)
    activate(volume, {meta["kind"]: run_id}, meta["created_at"], keep_runs)


def prune_runs(volume: Volume, kind: str, keep_runs: int):
    # по времени записи на диск: виртуальное время в имени при остановленных часах одинаковое
    runs = [p for p in volume.runs.glob(f"{kind}-*") if not p.name.endswith(".tmp")]
    runs.sort(key=lambda p: p.stat().st_mtime_ns)
    for old in runs[:-keep_runs]:
        shutil.rmtree(old)


def publish_reference(volume: Volume):
    calendar = load_calendar()
    features = calendar.merge(load_day_features(calendar), on="date")
    write_atomic(volume.calendar, lambda tmp: features.to_parquet(tmp, index=False))
    write_atomic(
        volume.correction_factors, lambda tmp: shutil.copyfile(CORRECTION_FACTORS_PATH, tmp)
    )
