import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from mtml.ingest.seed import apply_seed
from mtml.ingest.settings import IngestSettings
from mtml.storage import Volume
from mtml.worker.schedule import load_state, rerun_reason
from mtml.worker.settings import WorkerSettings

SETTINGS = IngestSettings(routes=(25,))
NOW = datetime(2025, 10, 1, 3, 0)
REAL = datetime(2026, 9, 27, 12, 0)


def make_seed(root: Path, cutoff: str):
    ts = pd.date_range("2025-08-01", "2025-09-30 23:00", freq="h")
    actuals = pd.DataFrame({"route": 25, "ts": ts, "boardings": 100})
    root.mkdir(parents=True)
    actuals.to_parquet(root / "actuals_hourly.parquet", index=False)
    pair = {"data_cutoff": cutoff, "schema_version": 1, "short": "short-a", "year": "year-a"}
    for run_id in ("short-a", "year-a"):
        (root / "runs" / run_id).mkdir(parents=True)
        (root / "runs" / run_id / "meta.json").write_text("{}")
    (root / "pairs.json").write_text(json.dumps([pair]))
    return root


def test_seed_is_laid_out_on_empty_volume_and_worker_does_not_rerun(tmp_path: Path):
    volume = Volume(tmp_path / "data")
    seed = make_seed(tmp_path / "seed", "2025-09-30")

    assert apply_seed(volume, seed, SETTINGS, NOW, REAL)["short"] == "short-a"

    active = json.loads(volume.active.read_text())
    assert (active["short"], active["year"]) == ("short-a", "year-a")
    assert (volume.runs / "year-a" / "meta.json").exists()
    state = load_state(volume)
    assert state.last_watermark == date(2025, 9, 30)
    # сразу после старта пересчитывать нечего: знак тот же, ночь ещё не наступила
    later = datetime(2025, 10, 1, 20, 0)
    assert rerun_reason(state, date(2025, 9, 30), later, REAL, WorkerSettings()) is None


def test_seed_for_other_watermark_is_skipped_but_facts_are_copied(tmp_path: Path):
    volume = Volume(tmp_path / "data")
    seed = make_seed(tmp_path / "seed", "2025-08-31")

    assert apply_seed(volume, seed, SETTINGS, NOW, REAL) is None
    assert volume.actuals.exists()
    assert not volume.active.exists()
    assert not volume.worker_state.exists()


@pytest.mark.parametrize("existing", ["active", "no_manifest"])
def test_seed_does_not_touch_published_volume(tmp_path: Path, existing: str):
    volume = Volume(tmp_path / "data")
    seed = make_seed(tmp_path / "seed", "2025-09-30")
    if existing == "active":
        volume.active.parent.mkdir(parents=True)
        volume.active.write_text('{"short": "mine"}')
    else:
        (seed / "pairs.json").unlink()

    assert apply_seed(volume, seed, SETTINGS, NOW, REAL) is None
    assert not volume.runs.exists()
