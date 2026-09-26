import json
from dataclasses import dataclass
from datetime import date

import pandas as pd

from mtml.data import to_hourly_grid
from mtml.storage import Volume


@dataclass(frozen=True)
class Context:
    series: pd.DataFrame
    watermark: date
    routes: tuple[int, ...]
    cold_start_routes: tuple[int, ...]


def build_context(volume: Volume, routes: tuple[int, ...]):
    """
    История до водяного знака на плотной сетке; маршруты без единой посадки — cold start.
    """
    mark = json.loads(volume.watermark.read_text(encoding="utf-8"))["watermark"]
    if mark is None:
        raise ValueError("Водяного знака ещё нет: ingest не загрузил ни одного полного дня")
    mark = date.fromisoformat(mark)

    actuals = pd.read_parquet(volume.actuals)
    actuals = actuals[actuals["ts"] < pd.Timestamp(mark) + pd.Timedelta(days=1)]
    with_history = tuple(r for r in routes if r in set(actuals["route"]))
    cold = tuple(r for r in routes if r not in with_history)
    observed = actuals.rename(columns={"boardings": "y"}).astype({"route": int, "y": float})

    # пропущенный день маршрута заполняется тем же днём недели соседних недель
    series = to_hourly_grid(
        observed[["route", "ts", "y"]], actuals["ts"].min().normalize(), mark, with_history
    )
    return Context(series, mark, with_history, cold)
