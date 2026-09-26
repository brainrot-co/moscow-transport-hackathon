import numpy as np
import pandas as pd

from mtml.data import MODEL_ROUTES, ROOT
from mtml.geo import distance_to_route_m, load_stop_sequences

EXTERNAL_DIR = ROOT / "dataset" / "external"
CALENDAR_PATH = EXTERNAL_DIR / "calendar.csv"
WEATHER_PATH = EXTERNAL_DIR / "weather_moscow_2025.csv"
SCHOOL_PATH = EXTERNAL_DIR / "school_holidays_moscow.csv"
# выгрузка событий KudaGo API v1.4 (https://docs.kudago.com/api/), location=msk
EVENTS_PATH = EXTERNAL_DIR / "kudago_events.csv"

CALENDAR = ("is_non_working", "is_holiday_weekday", "is_shortened")
WEATHER = ("temperature", "precipitation", "snowfall")
SCHOOL = ("school_holiday_modular", "school_holiday_quarter")
EVENTS = ("events_near",)
DAY_TYPE = ("day_type",)
HOLIDAY_PROXIMITY = ("days_to_holiday", "days_after_holiday")
# дальше недели близость к празднику уже не важна: такие дни получают это значение
HOLIDAY_PROXIMITY_MAX = 7

# событие «рядом с маршрутом» — до ближайшей остановки не дальше этого
EVENT_RADIUS_M = 800
# пассажиры едут к событию и от него: окно шире самого события
EVENT_PAD = pd.Timedelta(hours=1)
# без конца в KudaGo — считаем, что событие длится столько
EVENT_DEFAULT_DURATION = pd.Timedelta(hours=2)
# длинные «события» (выставки, спектакли на сезон) — это фон, а не всплеск
EVENT_MAX_DURATION = pd.Timedelta(hours=12)


def load_calendar():
    calendar = pd.read_csv(CALENDAR_PATH, parse_dates=["date"])
    return calendar[["date", *CALENDAR]]


def load_day_features(calendar: pd.DataFrame):
    # праздничный блок — подряд идущие нерабочие дни хотя бы с одним нерабочим будним днём
    # (праздник или перенос): новогодние, майские, 2–4 ноября; обычные выходные блоком не считаются
    cal = calendar.sort_values("date").reset_index(drop=True)
    off = cal["is_non_working"].astype(bool)
    run = (off != off.shift()).cumsum()
    in_block = off & cal.groupby(run)["is_holiday_weekday"].transform("max").astype(bool)

    dow = cal["date"].dt.dayofweek
    day_type = pd.Series("workday", index=cal.index)
    day_type[off & (dow == 5)] = "saturday"
    day_type[off & (dow == 6)] = "sunday"
    day_type[in_block] = "holiday"
    starts = in_block & ~in_block.shift(fill_value=False)
    ends = in_block & ~in_block.shift(-1, fill_value=False)
    work = ~off
    for flags, direction, label in ((starts, -1, "pre_holiday"), (ends, 1, "post_holiday")):
        for i in flags[flags].index:
            j = i + direction
            while 0 <= j < len(cal) and not work[j]:
                j += direction
            if 0 <= j < len(cal) and day_type[j] == "workday":
                day_type[j] = label
    day_type[(cal["is_shortened"] == 1) & (day_type == "workday")] = "pre_holiday"

    idx = pd.Series(range(len(cal)), dtype=float)
    next_start = idx.where(starts).bfill()
    prev_end = idx.where(ends).ffill()
    return pd.DataFrame(
        {
            "date": cal["date"],
            "day_type": day_type,
            "days_to_holiday": (next_start - idx)
            .where(~in_block, 0)
            .fillna(HOLIDAY_PROXIMITY_MAX)
            .clip(upper=HOLIDAY_PROXIMITY_MAX),
            "days_after_holiday": (idx - prev_end)
            .where(~in_block, 0)
            .fillna(HOLIDAY_PROXIMITY_MAX)
            .clip(upper=HOLIDAY_PROXIMITY_MAX),
        }
    )


def load_school_holidays(dates: pd.DatetimeIndex):
    periods = pd.read_csv(SCHOOL_PATH, parse_dates=["start", "end"])
    out = pd.DataFrame({"date": dates})
    for system in ("modular", "quarter"):
        flag = np.zeros(len(dates), dtype=int)
        for p in periods[periods["system"] == system].itertuples():
            flag |= ((dates >= p.start) & (dates <= p.end)).astype(int)
        out[f"school_holiday_{system}"] = flag
    return out


def load_events_near_routes(hours: pd.DatetimeIndex, radius_m: float = EVENT_RADIUS_M):
    raw = pd.read_csv(EVENTS_PATH).dropna(subset=["event_lat", "event_lon", "event_start"])
    start = (
        pd.to_datetime(raw["event_start"], utc=True)
        .dt.tz_convert("Europe/Moscow")
        .dt.tz_localize(None)
    )
    end = pd.to_datetime(raw["event_end"], utc=True, errors="coerce")
    end = end.dt.tz_convert("Europe/Moscow").dt.tz_localize(None)
    end = end.where(end > start, start + EVENT_DEFAULT_DURATION)
    events = pd.DataFrame(
        {"lat": raw["event_lat"], "lon": raw["event_lon"], "start": start, "end": end}
    )
    events = events[
        (events["end"] - events["start"] <= EVENT_MAX_DURATION)
        & (events["end"] >= hours.min())
        & (events["start"] <= hours.max())
    ]
    # одно и то же занятие события встречается в выгрузке KudaGo несколько раз
    events = events.drop_duplicates().reset_index(drop=True)

    dist = distance_to_route_m(
        events["lat"].to_numpy(), events["lon"].to_numpy(), load_stop_sequences()
    )
    near = dist.stack().rename_axis(["event", "route"]).rename("dist").reset_index()
    near = near[near["dist"] <= radius_m].join(events, on="event")

    first = (near["start"] - EVENT_PAD).dt.floor("h")
    n_hours = ((near["end"] + EVENT_PAD).dt.floor("h") - first) // pd.Timedelta(hours=1) + 1
    rows = near.loc[near.index.repeat(n_hours), ["route"]]
    offsets = np.concatenate([np.arange(n) for n in n_hours])
    rows["ts"] = first.repeat(n_hours).to_numpy() + pd.to_timedelta(offsets, unit="h")
    counts = rows.groupby(["route", "ts"]).size().rename("events_near")

    index = pd.MultiIndex.from_product([list(MODEL_ROUTES), hours], names=["route", "ts"])
    return counts.reindex(index, fill_value=0).reset_index()


def load_hourly_covariates(
    columns: tuple[str, ...], start: str = "2025-01-01", end: str = "2026-12-31"
):
    """Календарь и каникулы есть всегда; погода и события — только если модель их просит.

    Погода есть только за историю, на горизонте прогноза она NaN.
    """
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    days = pd.DataFrame({"ts": hours, "date": hours.normalize()})
    calendar = load_calendar()
    daily = calendar.merge(load_day_features(calendar), on="date")
    daily = daily.merge(load_school_holidays(hours.normalize().unique()), on="date")
    common = days.merge(daily, on="date", how="left").drop(columns="date")
    # погода, события и остановки нужны только экспериментальным моделям: их файлов
    # нет в образе воркера, поэтому они читаются лишь по запросу
    if set(columns) & set(WEATHER):
        common = common.merge(pd.read_csv(WEATHER_PATH, parse_dates=["ts"]), on="ts", how="left")
    if set(columns) & set(EVENTS):
        return load_events_near_routes(hours).merge(common, on="ts", how="left")
    routes = pd.DataFrame({"route": list(MODEL_ROUTES)})
    return routes.merge(common, how="cross")
