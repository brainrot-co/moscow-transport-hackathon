import json
import logging
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from mtml.clock import real_now
from mtml.data import ROOT
from mtml.ingest.pipeline import refresh_status
from mtml.ingest.settings import IngestSettings
from mtml.storage import Volume
from mtml.worker.context import build_context
from mtml.worker.publish import SCHEMA_VERSION, publish_reference, write_run
from mtml.worker.settings import WorkerSettings
from mtml.worker.short import build_short
from mtml.worker.year import build_year

log = logging.getLogger("build_seed")

SEED = ROOT / "ml" / "seed"


def demo_start():
    compose = (ROOT / "compose.demo.yml").read_text(encoding="utf-8")
    starts = set(re.findall(r'CLOCK_START:\s*"([^"]+)"', compose))
    if len(starts) != 1:
        raise ValueError(f"В compose.demo.yml у сервисов разный CLOCK_START: {starts}")
    return datetime.fromisoformat(starts.pop())


def build_pair(actuals: Path, now: datetime, settings: WorkerSettings, runs: Path):
    with tempfile.TemporaryDirectory() as tmp:
        volume = Volume(Path(tmp))
        volume.actuals.parent.mkdir(parents=True)
        shutil.copy2(actuals, volume.actuals)
        refresh_status(volume, IngestSettings.from_env(), now)
        context = build_context(volume, settings.routes)
        pair = {"data_cutoff": str(context.watermark), "schema_version": SCHEMA_VERSION}
        for build in (build_short, build_year):
            run_id, tables, meta = build(volume, context, settings, now)
            write_run(volume, run_id, tables, meta)
            shutil.copytree(volume.runs / run_id, runs / run_id)
            pair[meta["kind"]] = run_id
        return pair | {"model": settings.model, "now": str(now)}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    actuals = Volume.from_env().actuals
    settings = WorkerSettings.from_env()
    seed = Volume(SEED)
    shutil.rmtree(SEED, ignore_errors=True)
    seed.runs.mkdir(parents=True)
    seed.actuals.parent.mkdir(parents=True)
    shutil.copy2(actuals, seed.actuals)
    publish_reference(seed)

    pairs = []
    for label, now in (("демо", demo_start()), ("прод", real_now())):
        log.info("Стартовый прогноз для режима %s, сейчас %s", label, now)
        pair = build_pair(actuals, now, settings, seed.runs)
        pairs.append(pair)
    (SEED / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2), "utf-8")
    log.info("Готово: %s", ", ".join(p["data_cutoff"] for p in pairs))


if __name__ == "__main__":
    main()
