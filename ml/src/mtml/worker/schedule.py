import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from mtml.clock import Clock, real_now
from mtml.storage import Volume, write_json_atomic
from mtml.worker.monitor import evaluate_runs
from mtml.worker.quality import QualityError
from mtml.worker.settings import WorkerSettings
from mtml.worker.short import run_short
from mtml.worker.year import run_year

log = logging.getLogger(__name__)


@dataclass
class WorkerState:
    last_run_real: datetime | None = None
    last_run_virtual: datetime | None = None
    last_watermark: date | None = None
    last_error: str | None = None


def load_state(volume: Volume):
    if not volume.worker_state.exists():
        return WorkerState()
    saved = json.loads(volume.worker_state.read_text(encoding="utf-8"))
    return WorkerState(
        last_run_real=datetime.fromisoformat(saved["last_run_real"]),
        last_run_virtual=datetime.fromisoformat(saved["last_run_virtual"]),
        last_watermark=date.fromisoformat(saved["last_watermark"]),
        last_error=saved["last_error"],
    )


def read_watermark(volume: Volume):
    if not volume.watermark.exists():
        return None
    mark = json.loads(volume.watermark.read_text(encoding="utf-8"))["watermark"]
    return date.fromisoformat(mark) if mark else None


def rerun_reason(
    state: WorkerState,
    watermark: date | None,
    virtual_now: datetime,
    real: datetime,
    settings: WorkerSettings,
):
    """Почему пора пересчитать прогноз, или None, если не пора."""
    if watermark is None:
        return None
    if state.last_run_real is None:
        return "первый прогон"
    # любой пересчёт не чаще раза в MIN_RERUN_MINUTES реальных минут: при ускоренных часах демо
    # и виртуальная ночь, и сдвиг водяного знака наступают каждые несколько секунд
    if real - state.last_run_real < timedelta(minutes=settings.min_rerun_minutes):
        return None
    if watermark != state.last_watermark:
        return f"водяной знак {state.last_watermark} → {watermark}"
    nightly = datetime.combine(virtual_now.date(), settings.run_at)
    if state.last_run_virtual < nightly <= virtual_now:
        return "ночной прогон"
    return None


def tick(volume: Volume, settings: WorkerSettings, virtual_now: datetime, real: datetime):
    state = load_state(volume)
    watermark = read_watermark(volume)
    reason = rerun_reason(state, watermark, virtual_now, real, settings)
    if reason is None:
        return None

    log.info("Пересчёт прогноза: %s", reason)
    state.last_error = None
    for run in (run_short, run_year):
        try:
            run(volume, settings, virtual_now)
        except QualityError as error:
            # прогноз не прошёл проверки: бэкенд остаётся на прежнем, следующая попытка —
            # при следующем сдвиге водяного знака или ночью
            log.warning("%s не опубликован, остаётся прежний: %s", run.__name__, error)
            state.last_error = f"{run.__name__}: {error}"
    state.last_run_real, state.last_run_virtual = real, virtual_now
    state.last_watermark = watermark
    write_json_atomic(volume.worker_state, asdict(state))
    evaluate_runs(volume, virtual_now)
    return reason


def run_forever(volume: Volume, settings: WorkerSettings, clock: Clock):
    while True:
        try:
            tick(volume, settings, clock.now(), real_now())
        except (ValueError, OSError) as error:
            # данных ещё нет или файл тома недописан — сервис не падает, пробует снова
            log.error("Прогон не удался: %s", error)
        time.sleep(settings.poll_sec)
