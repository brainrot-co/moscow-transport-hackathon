from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.core.logger import logger
from app.schemas.correction_factors import CorrectionFactorsRead

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
        self._active: dict[str, Any] = {}
        self._clock: dict[str, Any] = {}
        self.correction_factors: CorrectionFactorsRead | None = None

    @property
    def snapshot(self) -> ForecastSnapshot | None:
        return self._snapshot

    async def replace(self, snapshot: ForecastSnapshot) -> None:
        async with self._lock:
            self._snapshot = snapshot
            self.last_error = None

    @property
    def published_at(self) -> datetime | None:
        value = self._active.get("published_at")
        return datetime.fromisoformat(str(value)) if value else None

    def now(self) -> datetime:
        real_now = datetime.now(ZoneInfo("Europe/Moscow")).replace(
            tzinfo=None, microsecond=0
        )
        virtual_start = _optional_datetime(self._clock.get("virtual_start"))
        if virtual_start is None:
            return real_now
        real_start = _optional_datetime(self._clock.get("real_start")) or real_now
        speed = float(self._clock.get("speed", 0))
        current = virtual_start + (real_now - real_start) * speed
        virtual_end = _optional_datetime(self._clock.get("virtual_end"))
        return min(current, virtual_end) if virtual_end else current

    async def load(self) -> bool:
        # справочник не зависит от прогноза: интерфейсу он нужен и без снапшота
        self._load_correction_factors()
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
        if int(active.get("schema_version", -1)) != short_meta.schema_version:
            raise SnapshotError("active.json schema_version does not match active runs")
        short = self._read_forecasts(short_id)
        year = self._read_forecasts(year_id)
        effects = self._read_effects(short_id)
        day_status = self._read_day_status()
        actuals = self._read_actuals(day_status)
        watermark_data = self._read_json("state/watermark.json", {})
        watermark = date.fromisoformat(watermark_data["watermark"])
        clock = self._read_json("state/clock.json", {})
        snapshot = ForecastSnapshot(
            actuals=actuals,
            short=short,
            year=year,
            effects=effects,
            short_meta=short_meta,
            year_meta=year_meta,
            watermark=watermark,
            day_types=self._read_day_types(),
            daily_actuals=_daily_totals(actuals, watermark),
        )
        self._active = active
        self._clock = clock
        return snapshot

    def _load_correction_factors(self) -> None:
        path = self.data_dir / "reference/correction_factors.json"
        if not path.exists():
            return
        try:
            self.correction_factors = CorrectionFactorsRead.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            # битый файл не сбрасывает уже загруженный справочник
            logger.warning("reference/correction_factors.json не прочитан: %s", exc)

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
            cold_start_routes=frozenset(
                int(route) for route in raw.get("cold_start_routes", [])
            ),
            model_name=model.get("name") or model.get("model"),
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

    def _read_actuals(
        self, day_status: dict[tuple[int, date], str]
    ) -> dict[tuple[int, datetime], ActualRecord]:
        rows = self._read_parquet("actuals/actuals_hourly.parquet")
        result: dict[tuple[int, datetime], ActualRecord] = {}
        for row in rows:
            record = ActualRecord(
                route=int(row["route"]),
                ts=_parse_timestamp(row["ts"]),
                value=int(row["boardings"]),
                status=day_status.get(
                    (int(row["route"]), _parse_timestamp(row["ts"]).date()),
                    str(row.get("status", "final")),
                ),
            )
            result[(record.route, record.ts)] = record
        return result

    def _read_day_status(self) -> dict[tuple[int, date], str]:
        path = self.data_dir / "actuals/day_status.parquet"
        if not path.exists():
            return {}
        return {
            (int(row["route"]), _parse_date(row["date"])): str(row["status"])
            for row in self._read_parquet("actuals/day_status.parquet")
        }

    def _read_effects(self, run_id: str) -> dict[tuple[int, date, str], float]:
        path = self.data_dir / f"runs/{run_id}/effects.parquet"
        if not path.exists():
            return {}
        rows = self._read_parquet(f"runs/{run_id}/effects.parquet")
        return {
            (
                int(row["route"]),
                _parse_date(row["date"]),
                str(row["factor"]),
            ): float(row["log_effect"])
            for row in rows
        }

    def _read_day_types(self) -> dict[date, str]:
        path = self.data_dir / "reference/calendar.parquet"
        if not path.exists():
            return {}
        return {
            _parse_date(row["date"]): str(row["day_type"])
            for row in self._read_parquet("reference/calendar.parquet")
        }

    def _read_parquet(self, path: str) -> list[dict[str, Any]]:
        import pyarrow.parquet as parquet

        return parquet.read_table(self.data_dir / path).to_pylist()


def _daily_totals(
    actuals: dict[tuple[int, datetime], ActualRecord], watermark: date
) -> dict[int, dict[date, int]]:
    # незавершённые дни (partial, missing) дают заниженную сумму и испортили бы норму
    totals: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for record in actuals.values():
        day = record.ts.date()
        if record.status == "final" and day <= watermark:
            totals[record.route][day] += record.value
    return {route: dict(days) for route, days in totals.items()}


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


def _optional_datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(str(value)) if value else None


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
