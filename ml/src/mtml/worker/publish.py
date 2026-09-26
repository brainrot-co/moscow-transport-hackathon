import json
import logging
import os
import shutil

import pandas as pd

from mtml.storage import Volume, write_json_atomic

SCHEMA_VERSION = 1

log = logging.getLogger(__name__)


def publish_run(
    volume: Volume,
    run_id: str,
    tables: dict[str, pd.DataFrame],
    meta: dict[str, object],
    keep_runs: int,
):
    """Прогон пишется во временную папку, переименовывается и лишь потом попадает в active.json."""
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

    active = {"schema_version": SCHEMA_VERSION}
    if volume.active.exists():
        active = json.loads(volume.active.read_text(encoding="utf-8"))
    active[meta["kind"]] = run_id
    active["published_at"] = meta["created_at"]
    write_json_atomic(volume.active, active)
    log.info("Опубликован прогон %s", run_id)
    prune_runs(volume, meta["kind"], keep_runs)


def prune_runs(volume: Volume, kind: str, keep_runs: int):
    # по времени записи на диск: виртуальное время в имени при остановленных часах одинаковое
    runs = [p for p in volume.runs.glob(f"{kind}-*") if not p.name.endswith(".tmp")]
    runs.sort(key=lambda p: p.stat().st_mtime_ns)
    for old in runs[:-keep_runs]:
        shutil.rmtree(old)
