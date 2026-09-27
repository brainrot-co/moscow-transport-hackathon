import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import numpy as np
import pandas as pd

from mtml.covariates import load_calendar, load_day_features, load_school_holidays
from mtml.forecasters.base import horizon_hours
from mtml.storage import Volume
from mtml.worker.context import Context, build_context
from mtml.worker.publish import SCHEMA_VERSION, publish_run
from mtml.worker.quality import check_forecast
from mtml.worker.settings import WorkerSettings
from mtml.worker.short import to_forecasts

log = logging.getLogger(__name__)

# уровень маршрута и суточный профиль — по последним неделям: за один год истории тренд
# не оценить, а свежий уровень ближе к будущему, чем средний за год
RECENT_WEEKS = 8
# эффекты типов дня считаются относительно обычного рабочего дня
DAY_TYPES = ("saturday", "sunday", "holiday", "pre_holiday", "post_holiday")
# суточный профиль у праздника такой же, как у воскресенья
DAY_KINDS = {"saturday": "saturday", "sunday": "day_off", "holiday": "day_off"}


@dataclass(frozen=True)
class RouteModel:
    months: list[int]
    coef: np.ndarray
    level_shift: float
    residual_q10: float
    residual_q90: float


def calendar_days(start: pd.Timestamp, end: pd.Timestamp):
    """[date, month, day_type, kind, school] на каждый день периода."""
    calendar = load_calendar()
    days = calendar.merge(load_day_features(calendar), on="date")[["date", "day_type"]]
    school = load_school_holidays(pd.date_range(start, end))
    school["school"] = school[["school_holiday_modular", "school_holiday_quarter"]].max(axis=1)
    days = days.merge(school[["date", "school"]], on="date")
    days["month"] = days["date"].dt.month
    days["kind"] = days["day_type"].map(DAY_KINDS).fillna("workday")
    return days


def design(days: pd.DataFrame, months: list[int]):
    columns = {"intercept": np.ones(len(days))}
    columns |= {f"month_{m}": (days["month"] == m).to_numpy(float) for m in months[1:]}
    columns |= {t: (days["day_type"] == t).to_numpy(float) for t in DAY_TYPES}
    columns["school"] = days["school"].to_numpy(float)
    return np.column_stack(list(columns.values()))


def fit_route(history: pd.DataFrame):
    """log1p(дневная сумма) = уровень + месяц + тип дня + каникулы, обычный МНК."""
    months = sorted(history["month"].unique())
    x, z = design(history, months), np.log1p(history["y"].to_numpy())
    coef, *_ = np.linalg.lstsq(x, z, rcond=None)
    residuals = z - x @ coef
    recent = history["date"] > history["date"].max() - pd.Timedelta(weeks=RECENT_WEEKS)
    q10, q90 = np.quantile(residuals, [0.1, 0.9])
    return RouteModel(months, coef, residuals[recent.to_numpy()].mean(), q10, q90)


def predict_route(model: RouteModel, future: pd.DataFrame):
    # месяца, которого нет в истории (при 10 месяцах данных — ноябрь и декабрь), модель не
    # видела: берётся эффект последнего наблюдённого, горизонт до конца года закрывает short
    last_month = model.months[-1]
    future = future.assign(
        month=future["month"].where(future["month"].isin(model.months), last_month)
    )
    z = design(future, model.months) @ model.coef + model.level_shift
    return pd.DataFrame(
        {
            "date": future["date"].to_numpy(),
            "kind": future["kind"].to_numpy(),
            "yhat": np.expm1(z),
            "q0.1": np.expm1(z + model.residual_q10),
            "q0.9": np.expm1(z + model.residual_q90),
        }
    )


def hourly_profile(series: pd.DataFrame, days: pd.DataFrame):
    """Доля каждого часа в дневной сумме по виду дня: рабочий, суббота, выходной или праздник."""
    frame = series.merge(days[["date", "kind"]], on="date")
    by_hour = frame.groupby(["kind", frame["ts"].dt.hour.rename("hour")])["y"].sum()
    return (by_hour / by_hour.groupby(level="kind").transform("sum")).rename("share")


def build_year(volume: Volume, context: Context, settings: WorkerSettings, now: datetime):
    """Считает и проверяет прогон, но не публикует: возвращает run_id, таблицы и meta."""
    start = pd.Timestamp(context.watermark) + pd.Timedelta(days=1)
    end = start + pd.Timedelta(days=settings.year_days - 1)

    # ремонты и пропуски — не обычный режим маршрута, на них годовая модель не учится
    status = pd.read_parquet(volume.day_status)
    usual = status.loc[(status["status"] == "final") & ~status["anomaly"], ["route", "date"]]
    series = context.series.assign(date=context.series["ts"].dt.normalize()).merge(
        usual, on=["route", "date"]
    )
    days = calendar_days(series["date"].min(), end)
    daily = series.groupby(["route", "date"])["y"].sum().reset_index().merge(days, on="date")
    future = days[days["date"].between(start, end)]
    unseen = sorted(set(future["month"]) - set(daily["month"]))
    log.info(
        "Годовой прогон: история по %s, прогноз %s – %s, месяцы без истории %s",
        context.watermark,
        start.date(),
        end.date(),
        unseen,
    )

    recent_from = series["date"].max() - pd.Timedelta(weeks=RECENT_WEEKS)
    preds = []
    for route in context.routes:
        model = fit_route(daily[daily["route"] == route])
        route_days = predict_route(model, future)
        recent = series[(series["route"] == route) & (series["date"] > recent_from)]
        profile = hourly_profile(recent, days).reset_index()
        hours = route_days.merge(profile, on="kind")
        hours["ts"] = hours["date"] + pd.to_timedelta(hours["hour"], unit="h")
        for column in ("yhat", "q0.1", "q0.9"):
            hours[column] = hours[column] * hours["share"]
        preds.append(hours.assign(route=route)[["route", "ts", "yhat", "q0.1", "q0.9"]])

    forecasts = to_forecasts(
        pd.concat(preds, ignore_index=True), context.cold_start_routes, horizon_hours(start, end)
    )
    checks = check_forecast(forecasts, context.series, settings.routes, start, end)

    run_id = f"year-{now:%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"
    meta = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "kind": "year",
        "created_at": now,
        "data_cutoff": context.watermark,
        "horizon": {"start": start, "end": end + pd.Timedelta(hours=23), "step": "hour"},
        "routes": list(settings.routes),
        "cold_start_routes": list(context.cold_start_routes),
        "model": {
            "name": "seasonal",
            "method": "log1p(дневная сумма) ~ месяц + тип дня + каникулы по маршруту; "
            f"уровень по последним {RECENT_WEEKS} неделям; часы по профилю вида дня",
            "months_without_history": unseen,
            "quantiles": [0.1, 0.9],
        },
        "quality_checks": checks,
    }
    return run_id, {"forecasts": forecasts}, meta


def run_year(
    volume: Volume, settings: WorkerSettings, now: datetime, context: Context | None = None
):
    context = context or build_context(volume, settings.routes)
    run_id, tables, meta = build_year(volume, context, settings, now)
    publish_run(volume, run_id, tables, meta, settings.keep_runs)
    return run_id
