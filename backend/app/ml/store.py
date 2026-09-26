from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import (
    ActualRecord,
    ForecastRecord,
    ForecastSnapshot,
    RunMetadata,
    SnapshotError,
)


class ForecastStore:
    """Atomic in-memory holder for the currently published ML snapshot."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self._snapshot: ForecastSnapshot | None = None
        self._lock = asyncio.Lock()
        self.last_error: str | None = None

    @property
    def snapshot(self) -> ForecastSnapshot | None:
        return self._snapshot

    async def replace(self, snapshot: ForecastSnapshot) -> None:
        async with self._lock:
            self._snapshot = snapshot
            self.last_error = None

    async def load(self) -> bool:
        try:
            snapshot = self._load_from_disk()
        except (OSError, ValueError, KeyError, SnapshotError, ImportError) as exc:
            self.last_error = str(exc)
            return False
        await self.replace(snapshot)
        return True

    def _load_from_disk(self) -> ForecastSnapshot:
        active_path = self.data_dir / "active.json"
        if not active_path.exists():
            raise SnapshotError("active.json is not available")
        active = json.loads(active_path.read_text(encoding="utf-8"))
        short_id = active.get("short")
        year_id = active.get("year")
        if not short_id or not year_id:
            raise SnapshotError("active.json must contain short and year run ids")

        short_meta = self._read_meta(short_id)
        year_meta = self._read_meta(year_id)
        short = self._read_forecasts(short_id)
        year = self._read_forecasts(year_id)
        effects = self._read_effects(short_id)
        actuals = self._read_actuals()
        watermark_data = self._read_json("state/watermark.json", {})
        watermark = date.fromisoformat(watermark_data["watermark"])
        return ForecastSnapshot(
            actuals=actuals,
            short=short,
            year=year,
            effects=effects,
            short_meta=short_meta,
            year_meta=year_meta,
            watermark=watermark,
        )

    def _read_meta(self, run_id: str) -> RunMetadata:
        raw = self._read_json(f"runs/{run_id}/meta.json")
        horizon = raw["horizon"]
        model = raw.get("model", {})
        return RunMetadata(
            run_id=raw["run_id"],
            kind=raw["kind"],
            schema_version=int(raw["schema_version"]),
            data_cutoff=date.fromisoformat(raw["data_cutoff"]),
            step=horizon["step"],
            routes=frozenset(int(route) for route in raw["routes"]),
            timezone=model.get("timezone", "Europe/Moscow"),
        )

    def _read_json(self, relative: str, default: Any = None) -> Any:
        path = self.data_dir / relative
        if not path.exists():
            if default is not None:
                return default
            raise SnapshotError(f"required file is missing: {relative}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_forecasts(
        self, run_id: str
    ) -> dict[tuple[int, datetime], ForecastRecord]:
        rows = self._read_parquet(f"runs/{run_id}/forecasts.parquet")
        result: dict[tuple[int, datetime], ForecastRecord] = {}
        for row in rows:
            record = ForecastRecord(
                route=int(row["route"]),
                ts=_parse_timestamp(row["ts"]),
                yhat=float(row["yhat"]),
                q10=_optional_float(row.get("q10")),
                q90=_optional_float(row.get("q90")),
            )
            result[(record.route, record.ts)] = record
        return result

    def _read_actuals(self) -> dict[tuple[int, datetime], ActualRecord]:
        rows = self._read_parquet("actuals/actuals_hourly.parquet")
        result: dict[tuple[int, datetime], ActualRecord] = {}
        for row in rows:
            record = ActualRecord(
                route=int(row["route"]),
                ts=_parse_timestamp(row["ts"]),
                value=int(row["boardings"]),
                status=str(row.get("status", "final")),
            )
            result[(record.route, record.ts)] = record
        return result

    def _read_effects(self, run_id: str) -> dict[tuple[int, date, str], float]:
        path = self.data_dir / f"runs/{run_id}/effects.parquet"
        if not path.exists():
            return {}
        rows = self._read_parquet(f"runs/{run_id}/effects.parquet")
        return {
            (
                int(row["route"]),
                date.fromisoformat(str(row["date"])),
                str(row["factor"]),
            ): float(row["log_effect"])
            for row in rows
        }

    def _read_parquet(self, path: str) -> list[dict[str, Any]]:
        import pyarrow.parquet as parquet

        return parquet.read_table(self.data_dir / path).to_pylist()


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except TypeError:
        pass
    return float(value)