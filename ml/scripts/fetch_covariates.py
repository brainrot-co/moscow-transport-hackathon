import argparse
import datetime as dt
import json
import urllib.request

import numpy as np
import pandas as pd

from mtml.covariates import CALENDAR_PATH, WEATHER_PATH

YEAR = 2025
ISDAYOFF_URL = "https://isdayoff.ru/api/getdata?year={year}&pre=1&cc=ru"
OPEN_METEO_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=55.7558&longitude=37.6173"
    "&start_date={start}&end_date={end}&hourly=temperature_2m,precipitation,snowfall"
    "&timezone=Europe%2FMoscow"
)
# погода нужна только как прошлая ковариата: история кончается 31 октября, а фактической
# погоды ноября–декабря на момент прогноза не было, поэтому её не скачиваем вовсе
WEATHER_START = dt.date(YEAR, 1, 1)
WEATHER_END = dt.date(YEAR, 10, 31)


def fetch_calendar(year: int):
    with urllib.request.urlopen(ISDAYOFF_URL.format(year=year), timeout=30) as response:
        codes = response.read().decode()
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    # 0 — рабочий, 1 — нерабочий, 2 — сокращённый (с pre=1)
    if len(codes) != len(dates) or set(codes) - {"0", "1", "2"}:
        raise ValueError(f"isDayOff вернул неожиданный ответ: {codes[:60]!r}")
    code = np.array([int(c) for c in codes])
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "is_non_working": (code == 1).astype(int),
            "is_holiday_weekday": ((code == 1) & (dates.dayofweek < 5)).astype(int),
            "is_shortened": (code == 2).astype(int),
        }
    )


def fetch_weather(start: dt.date, end: dt.date):
    url = OPEN_METEO_URL.format(start=start.isoformat(), end=end.isoformat())
    with urllib.request.urlopen(url, timeout=60) as response:
        hourly = json.load(response)["hourly"]
    weather = pd.DataFrame(
        {
            "ts": pd.to_datetime(hourly["time"]),
            "temperature": hourly["temperature_2m"],
            "precipitation": hourly["precipitation"],
            "snowfall": hourly["snowfall"],
        }
    )
    if weather.isna().any().any():
        raise ValueError("В погоде Open-Meteo есть пропуски")
    return weather


def main():
    argparse.ArgumentParser(
        description="Календарь isDayOff и погода Open-Meteo -> dataset/external/"
    ).parse_args()
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)

    calendar = fetch_calendar(YEAR)
    calendar.to_csv(CALENDAR_PATH, index=False)
    holidays = calendar[calendar["is_holiday_weekday"] == 1]["date"].tolist()
    print(f"Календарь: {len(calendar)} дней, праздники в будни: {holidays} -> {CALENDAR_PATH}")

    weather = fetch_weather(WEATHER_START, WEATHER_END)
    weather.to_csv(WEATHER_PATH, index=False)
    print(f"Погода: {len(weather)} ч, по {weather['ts'].max():%Y-%m-%d} -> {WEATHER_PATH}")


if __name__ == "__main__":
    main()
