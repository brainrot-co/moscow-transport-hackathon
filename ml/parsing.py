"""Загрузка внешних данных: производственный календарь и погода. Кэшируются на диске."""
import json
import urllib.request

import pandas as pd

CALENDAR_URL = "https://isdayoff.ru/api/getdata?year=2025&cc=ru&pre=1"
WEATHER_URL = ("https://archive-api.open-meteo.com/v1/archive?latitude=55.75&longitude=37.62"
               "&start_date=2025-01-01&end_date=2025-12-31&timezone=Europe%2FMoscow"
               "&daily=temperature_2m_mean,precipitation_sum,snowfall_sum")


def load_external_data(cache_dir) -> pd.DataFrame:
    """Таблица по дням 2025 года:
    day_off, shortened — производственный календарь РФ (isdayoff.ru: 0 рабочий, 1 выходной, 2 сокращённый);
    precipitation_sum, snowfall_sum, temperature_2m_mean — фактическая погода в Москве (Open-Meteo)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    calendar_path = cache_dir / "calendar_2025.csv"
    weather_path = cache_dir / "weather_moscow_2025.csv"

    if not calendar_path.exists():
        codes = urllib.request.urlopen(CALENDAR_URL).read().decode().strip()  # по символу на день
        calendar = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=len(codes)),
                                 "code": [int(code) for code in codes]})
        calendar["day_off"] = (calendar["code"] == 1).astype(int)
        calendar["shortened"] = (calendar["code"] == 2).astype(int)
        calendar.to_csv(calendar_path, index=False)

    if not weather_path.exists():
        daily = json.loads(urllib.request.urlopen(WEATHER_URL).read())["daily"]
        pd.DataFrame(daily).rename(columns={"time": "date"}).to_csv(weather_path, index=False)

    calendar = pd.read_csv(calendar_path, parse_dates=["date"], index_col="date")
    weather = pd.read_csv(weather_path, parse_dates=["date"], index_col="date")
    return calendar[["day_off", "shortened"]].join(
        weather[["precipitation_sum", "snowfall_sum", "temperature_2m_mean"]])
