import json
import logging

import numpy as np
import pandas as pd

from mtml.covariates import CALENDAR_PATH, EVENTS_PATH, EXTERNAL_DIR, SCHOOL_PATH, WEATHER_PATH
from mtml.data import ROOT
from mtml.geo import load_stop_sequences
from mtml.storage import Volume

log = logging.getLogger("check_correction_factors")

FACTORS_PATH = EXTERNAL_DIR / "correction_factors.json"
# меньше этого эффект не публикуется: интервал слишком широкий, чтобы что-то утверждать
MIN_SAMPLE = 5
BASE_WEEKS = 3
BOOTSTRAP = 1000
EVENT_RADIUS_M = 600
BIG_EVENTS = "concert|festival|party|sport"


def clean_days(volume: Volume):
    """Дни маршрутов без праздников, переносов, каникул, аномалий и недогрузки — база сравнения."""
    hourly = pd.read_parquet(volume.actuals)
    daily = (
        hourly.assign(date=hourly["ts"].dt.normalize())
        .groupby(["route", "date"])["boardings"]
        .sum()
        .rename("y")
        .reset_index()
    )
    status = pd.read_parquet(volume.day_status)[["route", "date", "status", "anomaly"]]
    calendar = pd.read_csv(CALENDAR_PATH, parse_dates=["date"])
    daily = daily.merge(status, on=["route", "date"]).merge(calendar, on="date", how="left")
    dow = daily["date"].dt.dayofweek
    special = (
        (daily["is_non_working"].eq(1) & (dow < 5))
        | daily["is_holiday_weekday"].eq(1)
        | daily["is_shortened"].eq(1)
        | (daily["is_non_working"].eq(0) & (dow >= 5))
    )
    school = pd.read_csv(SCHOOL_PATH, parse_dates=["start", "end"])
    holidays = pd.DatetimeIndex(
        np.concatenate(
            [
                pd.date_range(s, e).values
                for s, e in zip(school["start"], school["end"], strict=True)
            ]
        )
    )
    daily["clean"] = (
        daily["status"].eq("final")
        & ~daily["anomaly"]
        & ~special
        & ~daily["date"].isin(holidays)
        & (daily["y"] > 0)
    )
    return daily.assign(dow=dow)[["route", "date", "dow", "y", "clean"]]


def with_baseline(frame: pd.DataFrame, keys: list[str], eligible: pd.Series):
    """Медиана того же маршрута и дня недели (и часа) за ±3 недели по подходящим строкам."""
    pool = frame[eligible][[*keys, "date", "y"]].rename(
        columns={"date": "base_date", "y": "base_y"}
    )
    pairs = frame.reset_index().merge(pool, on=keys)
    gap = (pairs["base_date"] - pairs["date"]).abs()
    pairs = pairs[(gap > pd.Timedelta(0)) & (gap <= pd.Timedelta(weeks=BASE_WEEKS))]
    base = pairs.groupby("index")["base_y"].agg(["median", "size"])
    return frame.assign(base=base["median"].where(base["size"] >= 2))


def effect(log_ratio: pd.Series, groups: pd.Series, unit: str, name: str):
    per_group = log_ratio.groupby(groups).mean()
    n = len(per_group)
    if n < MIN_SAMPLE:
        return {"name": name, "effect": None, "ci": None, "n": n, "unit": unit}
    rng = np.random.default_rng(0)
    draws = rng.choice(per_group.to_numpy(), size=(BOOTSTRAP, n)).mean(axis=1)
    low, high = np.expm1(np.percentile(draws, [2.5, 97.5]))
    return {
        "name": name,
        "effect": round(float(np.expm1(per_group.mean())), 4),
        "ci": [round(float(low), 4), round(float(high), 4)],
        "n": n,
        "unit": unit,
    }


def weather_checks(days: pd.DataFrame, volume: Volume):
    weather = pd.read_csv(WEATHER_PATH, parse_dates=["ts"])
    daytime = weather[weather["ts"].dt.hour.between(6, 21)]
    by_day = daytime.groupby(daytime["ts"].dt.normalize().rename("date"))[
        ["precipitation", "snowfall"]
    ].sum()
    daily = with_baseline(days, ["route", "dow"], days["clean"]).merge(
        by_day, left_on="date", right_index=True
    )
    daily = daily[daily["clean"] & daily["base"].notna()]
    daily_log = np.log(daily["y"] / daily["base"])

    hourly = pd.read_parquet(volume.actuals).rename(columns={"boardings": "y"})
    hourly = hourly.assign(date=hourly["ts"].dt.normalize(), hour=hourly["ts"].dt.hour)
    hourly = hourly.merge(days[["route", "date", "dow", "clean"]], on=["route", "date"])
    hourly = hourly[hourly["clean"] & hourly["hour"].between(6, 22)].merge(weather, on="ts")
    dry = (hourly["precipitation"] < 0.1) & (hourly["snowfall"] < 0.1)
    hourly = with_baseline(hourly, ["route", "dow", "hour"], dry)
    # в часы с малым потоком отношение шумит сильнее самого эффекта
    hourly = hourly[hourly["base"] > 20]
    hourly_log = np.log(hourly["y"] / hourly["base"])
    rainy_hour = hourly["precipitation"].between(0.5, 2) & (hourly["snowfall"] < 0.1)

    return {
        "heavy_rain": [
            effect(
                daily_log[daily["precipitation"] >= 5],
                daily["date"],
                "дней",
                "дни с осадками ≥ 5 мм за 6–22 ч, как у L'Institut Paris Region",
            ),
            effect(
                hourly_log[rainy_hour], hourly["ts"], "часов", "часы с дождём 0,5–2 мм/ч, 6–22 ч"
            ),
        ],
        "heavy_snow": [
            effect(daily_log[daily["snowfall"] >= 2], daily["date"], "дней", "дни со снегом ≥ 2 см")
        ],
        "extreme_snow": [
            effect(
                daily_log[daily["snowfall"] >= 10], daily["date"], "дней", "дни со снегом ≥ 10 см"
            )
        ],
    }


def event_route_days():
    events = pd.read_csv(EVENTS_PATH, parse_dates=["event_start_date", "event_end_date"])
    events = events[
        events["event_lat"].notna()
        & events["categories"].str.contains(BIG_EVENTS, na=False)
        & ((events["event_end_date"] - events["event_start_date"]).dt.days <= 1)
    ]
    stops = load_stop_sequences()
    hits = []
    for route, route_stops in stops.groupby("route"):
        lat = np.radians(route_stops["lat"].to_numpy())[:, None]
        lon = np.radians(route_stops["lon"].to_numpy())[:, None]
        event_lat = np.radians(events["event_lat"].to_numpy())[None, :]
        event_lon = np.radians(events["event_lon"].to_numpy())[None, :]
        dx = (event_lon - lon) * np.cos((lat + event_lat) / 2)
        near = (6_371_000 * np.hypot(dx, event_lat - lat) < EVENT_RADIUS_M).any(axis=0)
        hits += [(route, day) for day in events["event_start_date"][near]]
    return pd.DataFrame(hits, columns=["route", "date"]).drop_duplicates()


def event_checks(days: pd.DataFrame):
    hits = event_route_days().assign(event=True)
    daily = days.merge(hits, on=["route", "date"], how="left").fillna({"event": False})
    daily = with_baseline(daily, ["route", "dow"], daily["clean"] & ~daily["event"])
    daily = daily[daily["clean"] & daily["event"] & daily["base"].notna()]
    name = f"концерты, фестивали, спорт в {EVENT_RADIUS_M} м от остановки (KudaGo)"
    return {"mass_event": [effect(np.log(daily["y"] / daily["base"]), daily["date"], "дней", name)]}


def disruption_checks(volume: Volume):
    status = pd.read_parquet(volume.day_status)
    calendar = pd.read_csv(CALENDAR_PATH, parse_dates=["date"])
    days = status[status["anomaly"]].merge(calendar, on="date", how="left")
    dow = days["date"].dt.dayofweek
    holiday = (
        (days["is_non_working"].eq(1) & (dow < 5))
        | days["is_holiday_weekday"].eq(1)
        | days["is_shortened"].eq(1)
    )
    # последний день выгрузки обрезан на 01:59 и выглядел бы как закрытие
    last_day = days["date"] == days["date"].max()
    days = days[~holiday & ~last_day].assign(share=lambda d: d["observed"] / d["expected"])
    closed = days[days["share"] < 0.1]
    shortened = days[days["share"].between(0.1, 0.9)]
    q25, median, q75 = shortened["share"].quantile([0.25, 0.5, 0.75])
    return {
        "route_shortened": [
            {
                "name": "аномальные дни не в праздники, посадок 10–90% от ожидаемого",
                "effect": round(float(median - 1), 4),
                "iqr": [round(float(q25 - 1), 4), round(float(q75 - 1), 4)],
                "n": len(shortened),
                "unit": "дней",
                "routes": sorted(int(r) for r in shortened["route"].unique()),
            }
        ],
        "route_closed": [
            {
                "name": "аномальные дни не в праздники, посадок меньше 10% от ожидаемого",
                "effect": round(float(closed["share"].median() - 1), 4),
                "n": len(closed),
                "unit": "дней",
                "routes": sorted(int(r) for r in closed["route"].unique()),
            }
        ],
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    volume = Volume.from_env()
    days = clean_days(volume)
    checks = weather_checks(days, volume) | event_checks(days) | disruption_checks(volume)

    factors = json.loads(FACTORS_PATH.read_text(encoding="utf-8"))
    for scenario in factors["scenario_types"]:
        scenario["local_check"] = checks.get(scenario["type"])
        for check in scenario["local_check"] or []:
            log.info("%s: %s", scenario["type"], check)
    text = json.dumps(factors, ensure_ascii=False, indent=2) + "\n"
    FACTORS_PATH.write_text(text, encoding="utf-8")
    log.info("Проверки записаны в %s", FACTORS_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
