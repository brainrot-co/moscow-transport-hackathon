from datetime import date
from functools import partial
from pathlib import Path

import duckdb

from mtml.storage import write_atomic

KEY = "device_no, tran_no, tran_date_time"


def copy_query(con: duckdb.DuckDBPyConnection, query: str, path: Path):
    con.execute(f"COPY ({query}) TO '{path}' (FORMAT parquet)")


def count_rows(con: duckdb.DuckDBPyConnection, path: Path):
    if not path.exists():
        return 0
    return con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]


def day_path(raw_dir: Path, day: date):
    return raw_dir / f"{day:%Y-%m-%d}.parquet"


def merge_raw(con: duckdb.DuckDBPyConnection, raw_dir: Path, batch_id: str):
    """Дописывает таблицу valid в файлы по дням без дублей; возвращает дни и число новых строк."""
    days = [
        row[0]
        for row in con.execute(
            "SELECT DISTINCT CAST(tran_date_time AS DATE) FROM valid ORDER BY 1"
        ).fetchall()
    ]
    new_rows = 0
    for day in days:
        path = day_path(raw_dir, day)
        fresh = (
            f"SELECT *, '{batch_id}' AS batch_id, 1 AS is_new FROM valid "
            f"WHERE CAST(tran_date_time AS DATE) = DATE '{day}'"
        )
        if path.exists():
            fresh = f"SELECT *, 0 AS is_new FROM read_parquet('{path}') UNION ALL BY NAME {fresh}"
        # при повторе ключа остаётся уже сохранённая строка, чтобы batch_id не переписывался
        merged = (
            f"SELECT * EXCLUDE (is_new) FROM ({fresh}) "
            f"QUALIFY row_number() OVER (PARTITION BY {KEY} ORDER BY is_new) = 1 "
            f"ORDER BY tran_date_time"
        )
        before = count_rows(con, path)
        write_atomic(path, partial(copy_query, con, merged))
        new_rows += count_rows(con, path) - before
    return days, new_rows
