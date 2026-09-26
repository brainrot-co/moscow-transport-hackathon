import argparse
import time
from pathlib import Path

import duckdb

# auto_detect выключен, поэтому перечислены все колонки файла в исходном порядке
COLUMNS = {
    "tran_no": "BIGINT",
    "device_no": "BIGINT",
    "tran_date_time": "TIMESTAMP",
    "begin_date_time": "TIMESTAMP",
    "input_date_time": "VARCHAR",
    "crd_hashcode": "VARCHAR",
    "validation_result": "INTEGER",
    "tran_type_id": "INTEGER",
    "place_id": "INTEGER",
    "good_type": "VARCHAR",
    "pass_route": "VARCHAR",
    "ngpt_route": "VARCHAR",
    "bus_exit_no": "INTEGER",
    "garage_number": "INTEGER",
}


def convert(sources: list[Path], out_dir: Path):
    missing = [str(p) for p in sources if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Нет файлов: {missing}")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"Папка {out_dir} не пустая: удалите её или укажите другую")

    files = ", ".join(f"'{p}'" for p in sources)
    columns = ", ".join(f"'{name}': '{kind}'" for name, kind in COLUMNS.items())
    con = duckdb.connect()
    # иначе DuckDB сохраняет порядок строк и копит их в памяти перед записью
    con.execute("SET preserve_insertion_order = false")
    # заголовок кончается на \n, строки данных на \r\n: на таком файле падают и
    # автоопределение формата, и параллельный ридер, поэтому формат задан вручную;
    # input_date_time по README местами битый, в Parquet его не берём
    query = f"""
        COPY (
            SELECT * EXCLUDE (input_date_time),
                year(tran_date_time) AS year,
                month(tran_date_time) AS month
            FROM read_csv(
                [{files}], delim = ';', header = true, auto_detect = false,
                columns = {{{columns}}}, new_line = '\\n', quote = '', escape = '',
                strict_mode = false, parallel = false
            )
        ) TO '{out_dir}' (FORMAT parquet, PARTITION_BY (year, month), COMPRESSION zstd)
    """
    return con.execute(query).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="CSV валидаций -> Parquet, разбитый по месяцам")
    parser.add_argument("sources", nargs="+", type=Path, help="например: train.csv test.csv")
    parser.add_argument("--out", type=Path, required=True, help="папка для Parquet")
    args = parser.parse_args()

    started = time.perf_counter()
    rows = convert(args.sources, args.out)
    size_gb = sum(f.stat().st_size for f in args.out.rglob("*.parquet")) / 1024**3
    elapsed = time.perf_counter() - started
    print(f"Записано {rows:,} строк, {size_gb:.2f} ГБ Parquet за {elapsed:.0f} с -> {args.out}")


if __name__ == "__main__":
    main()
