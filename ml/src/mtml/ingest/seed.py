import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from mtml.data import ROOT
from mtml.ingest.settings import IngestSettings
from mtml.ingest.status import day_status, watermark
from mtml.storage import Volume, write_json_atomic

log = logging.getLogger(__name__)


def seed_dir():
    """Стартовый прогноз, запечённый в образ ingest; собирает ml/scripts/build_seed.py."""
    return Path(os.environ.get("SEED_DIR", ROOT / "ml" / "seed"))


def apply_seed(volume: Volume, seed: Path, settings: IngestSettings, now: datetime, real: datetime):
    """Раскладывает стартовый прогноз на пустой том; None, если том не пуст или пары нет."""
    manifest = seed / "pairs.json"
    if volume.active.exists() or not manifest.exists():
        return None
    # календарь и справочник поправок бэкенд читает сразу, воркер перепишет их при своём старте
    for path in ("actuals", "calendar", "correction_factors"):
        source, target = getattr(Volume(seed), path), getattr(volume, path)
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    # знак считается тем же правилом, что в refresh_status, но в файл пока не пишется:
    # воркер не должен увидеть знак раньше, чем state/worker.json от стартового прогноза
    mark = watermark(day_status(pd.read_parquet(volume.actuals), now.date(), settings))
    pairs = json.loads(manifest.read_text(encoding="utf-8"))
    pair = next((p for p in pairs if p["data_cutoff"] == str(mark)), None)
    if pair is None:
        log.info("Стартового прогноза на водяной знак %s нет, воркер посчитает сам", mark)
        return None

    for kind in ("short", "year"):
        shutil.copytree(seed / "runs" / pair[kind], volume.runs / pair[kind], dirs_exist_ok=True)
    # воркер считает этот прогноз уже сделанным: следующий пересчёт — при сдвиге знака или ночью
    state = {"last_run_real": real, "last_run_virtual": now, "last_watermark": mark}
    write_json_atomic(volume.worker_state, state | {"last_error": None})
    active = {key: pair[key] for key in ("schema_version", "short", "year")}
    write_json_atomic(volume.active, active | {"published_at": now})
    log.info(
        "Стартовый прогноз разложен: %s и %s, водяной знак %s", pair["short"], pair["year"], mark
    )
    return pair
