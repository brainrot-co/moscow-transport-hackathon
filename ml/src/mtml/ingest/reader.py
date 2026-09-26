from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

from mtml.ingest.settings import IngestSettings

COLUMNS = (
    "tran_no",
    "device_no",
    "tran_date_time",
    "begin_date_time",
    "input_date_time",
    "crd_hashcode",
    "validation_result",
    "tran_type_id",
    "place_id",
    "good_type",
    "pass_route",
    "ngpt_route",
    "bus_exit_no",
    "garage_number",
)

# будущее с запасом на расхождение часов валидатора и сервера
FUTURE_TOLERANCE_HOURS = 1


@dataclass(frozen=True)
class ReadStats:
    rows_total: int
    rows_refused: int
    rows_quarantined: int
    rows_unknown_route: int
    rows_valid: int


def check_header(path: Path):
    with path.open(encoding="utf-8") as file:
        header = tuple(file.readline().rstrip("\r\n").split(";"))
    if header != COLUMNS:
        raise ValueError(f"Неожиданный заголовок в {path.name}: {';'.join(header)}")


def load_batch(con: duckdb.DuckDBPyConnection, path: Path, now: datetime, settings: IngestSettings):
    """Создаёт в con таблицы checked (все строки с причиной отбраковки) и valid (посадки)."""
    check_header(path)
    columns = ", ".join(f"'{name}': 'VARCHAR'" for name in COLUMNS)
    source = str(path).replace("'", "''")
    # заголовок кончается на \n, строки данных на \r\n: автоопределение формата на таком
    # файле падает, поэтому формат задан вручную, а \r срезается с последней колонки
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE parsed AS
        SELECT
            TRY_CAST(device_no AS BIGINT) AS device_no,
            TRY_CAST(tran_no AS BIGINT) AS tran_no,
            TRY_CAST(tran_date_time AS TIMESTAMP) AS tran_date_time,
            TRY_CAST(input_date_time AS TIMESTAMP) AS input_date_time,
            TRY_CAST(validation_result AS INTEGER) AS validation_result,
            TRY_CAST(regexp_extract(ngpt_route, '^\\s*(\\d+)', 1) AS INTEGER) AS route,
            ngpt_route,
            TRY_CAST(rtrim(garage_number, chr(13)) AS INTEGER) AS garage_number
        FROM read_csv('{source}', delim=';', header=true, auto_detect=false,
                      columns={{{columns}}}, new_line='\\n', quote='', escape='',
                      strict_mode=false, parallel=false)
    """)
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE checked AS
        SELECT *,
            CASE
                WHEN device_no IS NULL OR tran_no IS NULL OR tran_date_time IS NULL
                     OR validation_result IS NULL THEN 'bad_value'
                WHEN tran_date_time > $now + to_hours($tolerance) THEN 'future'
                WHEN tran_date_time < $min_date THEN 'too_old'
                WHEN validation_result = 1 AND route IS NULL THEN 'no_route'
            END AS reason
        FROM parsed
        """,
        {"now": now, "tolerance": FUTURE_TOLERANCE_HOURS, "min_date": settings.min_date},
    )
    con.execute("""
        CREATE OR REPLACE TEMP TABLE valid AS
        SELECT device_no, tran_no, tran_date_time, input_date_time, route, garage_number
        FROM checked
        WHERE reason IS NULL AND validation_result = 1
        ORDER BY tran_date_time
    """)
    total, refused, quarantined, unknown = con.execute(
        """
        SELECT
            count(*),
            count(*) FILTER (WHERE reason IS NULL AND validation_result <> 1),
            count(*) FILTER (WHERE reason IS NOT NULL),
            count(*) FILTER (WHERE reason IS NULL AND validation_result = 1
                             AND NOT list_contains($routes, route))
        FROM checked
        """,
        {"routes": list(settings.routes)},
    ).fetchone()
    valid = total - refused - quarantined
    return ReadStats(total, refused, quarantined, unknown, valid)
