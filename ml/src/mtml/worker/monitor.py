import json
import logging
from datetime import datetime

import pandas as pd

from mtml.metrics import wape_score
from mtml.storage import Volume, write_atomic

log = logging.getLogger(__name__)

# на сколько дней вперёд от водяного знака был прогноз: точность падает с дальностью
LEADS = ((1, 1, "1 день"), (2, 7, "2–7 дней"), (8, 30, "8–30 дней"), (31, 366, "31+ дней"))


def evaluate_run(run: pd.DataFrame, meta: dict[str, object], facts: pd.DataFrame):
    cutoff = pd.Timestamp(meta["data_cutoff"])
    run = run[~run["route"].isin(meta["cold_start_routes"])]
    both = run.merge(facts, on=["route", "ts"])
    lead = (both["ts"].dt.normalize() - cutoff).dt.days
    rows = []
    for first, last, label in LEADS:
        part = both[lead.between(first, last)]
        if part.empty or part["y"].sum() == 0:
            continue
        rows.append(
            {
                "run_id": meta["run_id"],
                "kind": meta["kind"],
                "model": meta["model"]["name"],
                "data_cutoff": cutoff,
                "lead": label,
                "days": part["ts"].dt.normalize().nunique(),
                "wape_score": wape_score(part["y"], part["yhat"].round()),
                "bias": part["yhat"].sum() / part["y"].sum() - 1,
            }
        )
    return rows


def evaluate_runs(volume: Volume, now: datetime):
    """Прогоны на диске против фактов за дни final; оценки удалённых прогонов сохраняются."""
    status = pd.read_parquet(volume.day_status)
    final = status.loc[status["status"] == "final", ["route", "date"]]
    actuals = pd.read_parquet(volume.actuals)
    facts = actuals.assign(date=actuals["ts"].dt.normalize()).merge(final, on=["route", "date"])
    facts = facts.rename(columns={"boardings": "y"})[["route", "ts", "y"]]

    rows = []
    for run_dir in sorted(volume.runs.glob("*")):
        if run_dir.name.endswith(".tmp"):
            continue
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        rows += evaluate_run(pd.read_parquet(run_dir / "forecasts.parquet"), meta, facts)
    if not rows:
        return pd.DataFrame()

    fresh = pd.DataFrame(rows).assign(evaluated_at=now)
    if volume.accuracy.exists():
        kept = pd.read_parquet(volume.accuracy)
        fresh = pd.concat([kept[~kept["run_id"].isin(fresh["run_id"])], fresh], ignore_index=True)
    write_atomic(volume.accuracy, lambda tmp: fresh.to_parquet(tmp, index=False))
    log.info("Точность прошлых прогонов обновлена: %d оценок", len(fresh))
    return fresh
