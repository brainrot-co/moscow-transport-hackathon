from functools import cache

from mtml.covariates import (
    CALENDAR,
    DAY_TYPE,
    EVENTS,
    HOLIDAY_PROXIMITY,
    SCHOOL,
    WEATHER,
    load_hourly_covariates,
)
from mtml.forecasters.base import Forecaster
from mtml.forecasters.chronos2 import Chronos2Forecaster
from mtml.forecasters.ensemble import EnsembleForecaster
from mtml.forecasters.naive import SeasonalNaive, WeeklyProfile
from mtml.forecasters.profile import (
    DAILY_CALENDAR,
    DAILY_VARIANTS,
    DAILY_WEATHER,
    DailyVariant,
    ProfileDailyForecaster,
)
from mtml.forecasters.xreg import XRegChronos

covariates = cache(load_hourly_covariates)


def _daily(future: tuple[str, ...] = (), past: tuple[str, ...] = ()):
    return Chronos2Forecaster(
        "route_hour_daily",
        covariates=covariates(future + past) if future or past else None,
        future_covariates=future,
        past_covariates=past,
    )


def _xreg(columns: tuple[str, ...], pool: str, base_future: tuple[str, ...] = ()):
    return XRegChronos(_daily(base_future), covariates(columns + base_future), columns, pool=pool)


def _ensemble(variants: tuple[DailyVariant, ...] = DAILY_VARIANTS):
    # у всех участников одна таблица: эффекты подменяют ковариаты сразу у всего ансамбля
    weather = WEATHER if any(set(DAILY_WEATHER) & set(f + p) for f, p in variants) else ()
    table = covariates(CALENDAR + SCHOOL + DAY_TYPE + weather)

    def member(future: tuple[str, ...]):
        return Chronos2Forecaster("route_hour_daily", covariates=table, future_covariates=future)

    return EnsembleForecaster(
        [
            member(CALENDAR + SCHOOL),
            member(CALENDAR + SCHOOL + DAY_TYPE),
            ProfileDailyForecaster(table, variants),
        ]
    )


def build(name: str):
    """Имя из реестра становится именем модели и run в MLflow."""
    registry = {
        "seasonal_naive": SeasonalNaive,
        "weekly_median_4w": lambda: WeeklyProfile(4, "median"),
        "weekly_mean_4w": lambda: WeeklyProfile(4, "mean"),
        "chronos2_hourly": lambda: Chronos2Forecaster("hourly"),
        "chronos2_hourly_xl": lambda: Chronos2Forecaster("hourly", cross_learning=True),
        "chronos2_daily": lambda: _daily(),
        "chronos2_daily_xl": lambda: Chronos2Forecaster("route_hour_daily", cross_learning=True),
        "chronos2_daily_cal": lambda: _daily(CALENDAR),
        "chronos2_daily_cal_wx": lambda: _daily(CALENDAR, WEATHER),
        "chronos2_daily_cal_school": lambda: _daily(CALENDAR + SCHOOL),
        "chronos2_daily_cal_events": lambda: _daily(CALENDAR + EVENTS),
        "chronos2_daily_cal_school_events": lambda: _daily(CALENDAR + SCHOOL + EVENTS),
        "chronos2_daily_all": lambda: _daily(CALENDAR + SCHOOL + EVENTS, WEATHER),
        "chronos2_daily_cal_school_daytype": lambda: _daily(CALENDAR + SCHOOL + DAY_TYPE),
        "chronos2_daily_cal_school_prox": lambda: _daily(CALENDAR + SCHOOL + HOLIDAY_PROXIMITY),
        "chronos2_daily_cal_school_daytype_prox": lambda: _daily(
            CALENDAR + SCHOOL + DAY_TYPE + HOLIDAY_PROXIMITY
        ),
        # тип дня вместо флагов календаря: он их включает
        "chronos2_daily_daytype_prox_school": lambda: _daily(DAY_TYPE + HOLIDAY_PROXIMITY + SCHOOL),
        "ensemble_cal_school_daytype_profile": _ensemble,
        # погода на горизонте известна (фактическая, как у лидерборда): только для экспериментов
        "ensemble_cal_school_daytype_profile_wx": lambda: _ensemble(
            DAILY_VARIANTS + ((DAILY_CALENDAR + tuple(DAILY_WEATHER), ()),)
        ),
        # погода только прошлой ковариатой: на горизонте её знать не нужно
        "ensemble_cal_school_daytype_profile_pwx": lambda: _ensemble(
            DAILY_VARIANTS + ((DAILY_CALENDAR, tuple(DAILY_WEATHER)),)
        ),
        "xreg_global_cal": lambda: _xreg(CALENDAR, "global"),
        "xreg_route_cal": lambda: _xreg(CALENDAR, "route"),
        "xreg_series_cal": lambda: _xreg(CALENDAR, "series"),
        "xreg_global_cal_school": lambda: _xreg(CALENDAR + SCHOOL, "global"),
        "xreg_route_cal_school": lambda: _xreg(CALENDAR + SCHOOL, "route"),
        "xreg_series_cal_school": lambda: _xreg(CALENDAR + SCHOOL, "series"),
        "xreg_route_cal_school_hybrid": lambda: _xreg(
            CALENDAR + SCHOOL, "route", CALENDAR + SCHOOL
        ),
    }
    if name not in registry:
        raise KeyError(f"Неизвестная модель {name!r}, есть: {sorted(registry)}")
    model = registry[name]()
    model.name = name
    return model


__all__ = [
    "Chronos2Forecaster",
    "EnsembleForecaster",
    "Forecaster",
    "ProfileDailyForecaster",
    "SeasonalNaive",
    "WeeklyProfile",
    "XRegChronos",
    "build",
]
