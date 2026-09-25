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
        return self.root / "inbox"

    @property
    def processed(self):
        return self.inbox / "processed"

    @property
    def failed(self):
        return self.inbox / "failed"

    @property
    def raw(self):
        return self.root / "raw" / "validations"

    @property
    def actuals(self):
        return self.root / "actuals" / "actuals_hourly.parquet"

    @property
    def day_status(self):
        return self.root / "actuals" / "day_status.parquet"

    @property
    def batches(self):
        return self.root / "ingestion" / "batches.parquet"

    @property
    def quarantine(self):
        return self.root / "ingestion" / "quarantine"

    @property
    def spill(self):
        return self.root / "tmp" / "duckdb"

    @property
    def watermark(self):
        return self.root / "state" / "watermark.json"


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
