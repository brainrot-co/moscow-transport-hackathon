import logging
from datetime import datetime
from uuid import uuid4

import pandas as pd

from mtml.forecasters import build
from mtml.forecasters.base import horizon_hours
from mtml.storage import Volume
from mtml.worker.context import Context, build_context
from mtml.worker.effects import compute_effects
from mtml.worker.publish import SCHEMA_VERSION, publish_run
from mtml.worker.quality import check_forecast
from mtml.worker.settings import WorkerSettings

log = logging.getLogger(__name__)


def to_forecasts(preds: pd.DataFrame, cold_start_routes: tuple[int, ...], hours: pd.DatetimeIndex):
    """Формат forecasts.parquet из контракта; у маршрутов без истории прогноз 0 без интервала."""
    forecasts = pd.DataFrame(
        {
            "route": preds["route"],
            "ts": preds["ts"],
            "yhat": preds["yhat"].clip(lower=0),
            "q10": preds.get("q0.1"),
            "q90": preds.get("q0.9"),
        }
    )
    cold = pd.MultiIndex.from_product([cold_start_routes, hours], names=["route", "ts"])
    cold = cold.to_frame(index=False).assign(yhat=0.0, q10=float("nan"), q90=float("nan"))
    return (
        pd.concat([forecasts, cold], ignore_index=True)
        .astype({"route": "int16", "q10": "float64", "q90": "float64"})
        .sort_values(["route", "ts"], ignore_index=True)
    )


def build_short(_volume: Volume, context: Context, settings: WorkerSettings, now: datetime):
    """Считает и проверяет прогон, но не публикует: возвращает run_id, таблицы и meta."""
    start = pd.Timestamp(context.watermark) + pd.Timedelta(days=1)
    end = start + pd.Timedelta(days=settings.horizon_days - 1)
    log.info(
        "Краткосрочный прогон %s: контекст по %s, прогноз %s – %s, маршруты без истории %s",
        settings.model,
        context.watermark,
        start.date(),
        end.date(),
        list(context.cold_start_routes),
    )

    forecaster = build(settings.model)
    preds = forecaster.fit(context.series).predict(start, end)
    forecasts = to_forecasts(preds, context.cold_start_routes, horizon_hours(start, end))
    checks = check_forecast(forecasts, context.series, settings.routes, start, end)
    effects = compute_effects(forecaster, forecasts, start, end)

    # при остановленных часах время не уникально, поэтому суффикс
    run_id = f"short-{now:%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"
    meta = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "kind": "short",
        "created_at": now,
        "data_cutoff": context.watermark,
        "horizon": {"start": start, "end": end + pd.Timedelta(hours=23), "step": "hour"},
        "routes": list(settings.routes),
        "cold_start_routes": list(context.cold_start_routes),
        "model": {
            "name": settings.model,
            "covariates": list(getattr(forecaster, "future_covariates", ())),
            "quantiles": list(getattr(forecaster, "quantiles", ())),
        },
        "quality_checks": checks,
        "effects": effects.groupby("factor")["date"].nunique().to_dict(),
    }
    return run_id, {"forecasts": forecasts, "effects": effects}, meta


def run_short(
    volume: Volume, settings: WorkerSettings, now: datetime, context: Context | None = None
):
    context = context or build_context(volume, settings.routes)
    run_id, tables, meta = build_short(volume, context, settings, now)
    publish_run(volume, run_id, tables, meta, settings.keep_runs)
    return run_id
