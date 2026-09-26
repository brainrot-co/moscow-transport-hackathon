import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mtml.data import ROOT


@dataclass(frozen=True)
class Volume:
    root: Path

    @classmethod
    def from_env(cls):
        return cls(Path(os.environ.get("DATA_DIR", ROOT / "data")))

    @property
    def inbox(self):
        """В inbox помещаются новые файлы, приходящие от стороннего сервиса"""
        return self.root / "inbox"

    @property
    def processed(self):
        """Файлы, успешно обработанные и перемещённые из inbox"""
        return self.inbox / "processed"

    @property
    def failed(self):
        """Файлы, которые не удалось обработать и перемещённые из inbox"""
        return self.inbox / "failed"

    @property
    def raw(self):
        """Сырые данные, которые прошли проверку и были скопированы из inbox
        Находятся на стадии между inbox и processed"""
        return self.root / "raw" / "validations"

    @property
    def actuals(self):
        """Посадки маршрут на час (route, ts, boardings)"""
        return self.root / "actuals" / "actuals_hourly.parquet"

    @property
    def day_status(self):
        """Статусы дней (day, route, status)"""
        return self.root / "actuals" / "day_status.parquet"

    @property
    def batches(self):
        """Журнал загрузок: по строке на файл — sha256, статус, счётчики строк, ошибка."""
        return self.root / "ingestion" / "batches.parquet"

    @property
    def quarantine(self):
        """Файлы, которые не прошли проверку и были перемещены из inbox"""
        return self.root / "ingestion" / "quarantine"

    @property
    def spill(self):
        """Сюда DuckDB сбрасывает данные сверх INGEST_MEMORY_LIMIT; после загрузки папка пустая."""
        return self.root / "tmp" / "duckdb"

    @property
    def watermark(self):
        """Водяной знак: до какой даты данные считаются полными и финализированными"""
        return self.root / "state" / "watermark.json"

    @property
    def clock(self):
        """Виртуальные часы, общие для всех сервисов; удалить файл — сбросить часы."""
        return self.root / "state" / "clock.json"

    @property
    def worker_state(self):
        """Когда и на каком водяном знаке воркер считал в последний раз, последняя ошибка."""
        return self.root / "state" / "worker.json"

    @property
    def accuracy(self):
        """Реальная точность опубликованных прогонов против пришедших фактов по горизонтам."""
        return self.root / "monitoring" / "accuracy.parquet"

    @property
    def runs(self):
        """Опубликованные прогоны: runs/<run_id>/ с прогнозом и meta.json."""
        return self.root / "runs"

    @property
    def active(self):
        """Указатель на активные прогоны; бэкенд читает прогноз только через него."""
        return self.root / "active.json"


def write_atomic(path: Path, write: Callable[[Path], object]):
    """Читатель видит либо прежний файл, либо новый целиком: запись во временный и rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json_atomic(path: Path, payload: dict[str, object]):
    # сериализация до записи: ошибка в данных не должна оставить полупустой файл
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    write_atomic(path, lambda tmp: tmp.write_text(text, encoding="utf-8"))
