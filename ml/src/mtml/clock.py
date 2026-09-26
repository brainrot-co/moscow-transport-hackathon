import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mtml.storage import write_json_atomic


def real_now():
    return datetime.now(ZoneInfo("Europe/Moscow")).replace(tzinfo=None, microsecond=0)


@dataclass(frozen=True)
class Clock:
    virtual_start: datetime | None
    real_start: datetime
    speed: float
    virtual_end: datetime | None

    def now(self):
        if self.virtual_start is None:
            return real_now()
        virtual = self.virtual_start + (real_now() - self.real_start) * self.speed
        virtual = virtual.replace(microsecond=0)
        return min(virtual, self.virtual_end) if self.virtual_end else virtual


def parse_time(value: str | None):
    return datetime.fromisoformat(value) if value else None


def load_clock(path: Path):
    '''Часы общие для всех контейнеров: первый запуск пишет state/clock.json из CLOCK_*.'''
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        return Clock(
            virtual_start=parse_time(saved["virtual_start"]),
            real_start=datetime.fromisoformat(saved["real_start"]),
            speed=float(saved["speed"]),
            virtual_end=parse_time(saved["virtual_end"]),
        )
    clock = Clock(
        virtual_start=parse_time(os.environ.get("CLOCK_START")),
        real_start=real_now(),
        speed=float(os.environ.get("CLOCK_SPEED", 0)),
        virtual_end=parse_time(os.environ.get("CLOCK_END")),
    )
    write_json_atomic(
        path,
        {
            "virtual_start": clock.virtual_start,
            "real_start": clock.real_start,
            "speed": clock.speed,
            "virtual_end": clock.virtual_end,
        },
    )
    return clock
