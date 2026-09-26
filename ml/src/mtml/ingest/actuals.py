from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from mtml.ingest.raw import day_path
from mtml.storage import write_atomic


def hourly_from_raw(con: duckdb.DuckDBPyConnection, raw_dir: Path, days: list[date]):
    """Посадки маршрут на час (route, ts, boardings) по всем сырым данным за дни days."""
    files = ", ".join(f"'{day_path(raw_dir, day)}'" for day in days)
    return con.execute(f"""
        WITH hourly AS (
            SELECT route, date_trunc('hour', tran_date_time) AS ts, count(*) AS boardings
            FROM read_parquet([{files}])
            GROUP BY ALL
        ),
        route_days AS (SELECT DISTINCT route, CAST(ts AS DATE) AS day FROM hourly),
        grid AS (
            SELECT route, CAST(day AS TIMESTAMP) + to_hours(hour) AS ts
            FROM route_days, range(24) AS hours(hour)
        )
        SELECT grid.route, grid.ts, coalesce(hourly.boardings, 0) AS boardings
        FROM grid LEFT JOIN hourly USING (route, ts)
    """).df()


def update_actuals(
    con: duckdb.DuckDBPyConnection,
    raw_dir: Path,
    actuals_path: Path,
    days: list[date],
    batch_id: str,
    now: datetime,
):
    """Затронутые дни пересчитываются по всем сырым данным целиком: повторы не удваиваются."""
    fresh = hourly_from_raw(con, raw_dir, days).assign(updated_at=now, batch_id=batch_id)
    if actuals_path.exists():
        kept = pd.read_parquet(actuals_path)
        kept = kept[~kept["ts"].dt.normalize().isin(pd.to_datetime(days))]
        fresh = pd.concat([kept, fresh], ignore_index=True)
    actuals = fresh.astype({"route": "int16", "boardings": "int32"}).sort_values(
        ["route", "ts"], ignore_index=True
    )
    write_atomic(actuals_path, lambda tmp: actuals.to_parquet(tmp, index=False))
    return actuals
