"""Подготовка данных: почасовые посадки из архива организаторов и признаки дня."""
import io
import zipfile

import numpy as np
import pandas as pd

HISTORY_HOURS = pd.date_range("2025-01-01 00:00", "2025-10-31 23:00", freq="h")

# Школьные каникулы Москвы (рекомендованные даты, лето включено).
# Четверти: https://www.rbc.ru/life/news/650956c49a7947086a7f6d64 (2024/25),
#           https://skillbox.ru/media/education/shkolnye-kanikuly-na-20252026-uchebnyy-god-raspisanie-po-chetvertyam-i-trimestram/ (2025/26)
# Модули:   https://spravke.livejournal.com/706247.html (2024/25),
#           https://www.rbc.ru/society/19/08/2025/68a42ae29a7947e5b7c1e219 (2025/26)
SCHOOL_HOLIDAYS = {
    "quarters": [("2024-12-28", "2025-01-12"), ("2025-03-22", "2025-03-30"), ("2025-05-27", "2025-08-31"),
                 ("2025-10-25", "2025-11-04"), ("2025-12-31", "2026-01-11")],
    "modular": [("2024-12-29", "2025-01-08"), ("2025-02-17", "2025-02-23"), ("2025-04-07", "2025-04-13"),
                ("2025-05-27", "2025-08-31"), ("2025-10-04", "2025-10-12"), ("2025-11-15", "2025-11-23"),
                ("2025-12-31", "2026-01-11")],
}


def load_dataset(path):
    """Читает dataset.zip. Возвращает:
    hourly   — посадки (успешные валидации): строки — часы 2025-01-01..10-31, столбцы — маршруты
               (часов без посадок в разметке нет, они заполняются нулями);
    template — сетка ответа route;date;hour."""
    with zipfile.ZipFile(path) as archive:
        tables = {name: pd.read_csv(io.BytesIO(archive.read(name)), sep=";")
                  for name in ("labels/labels_day_train.csv", "labels/labels_day_test.csv", "test_submission.csv")}

    labels = pd.concat([tables["labels/labels_day_train.csv"], tables["labels/labels_day_test.csv"]])
    labels["ts"] = pd.to_datetime(labels["date"]) + pd.to_timedelta(labels["hour"], unit="h")
    hourly = labels.pivot_table(index="ts", columns="route", values="boardings", aggfunc="sum")
    hourly = hourly.reindex(HISTORY_HOURS).fillna(0.0)
    return hourly, tables["test_submission.csv"][["route", "date", "hour"]]


def build_day_features(external: pd.DataFrame) -> pd.DataFrame:
    """Признаки дня, известные заранее: календарь, школьные каникулы, тип дня, погода."""
    days = external.copy()
    days["dow"] = days.index.dayofweek
    days["holiday"] = ((days["day_off"] == 1) & (days["dow"] < 5)).astype(int)        # выходной в будни
    days["work_weekend"] = ((days["day_off"] == 0) & (days["dow"] >= 5)).astype(int)  # рабочая суббота
    days["special"] = days["holiday"] | days["work_weekend"]

    for system, periods in SCHOOL_HOLIDAYS.items():
        days[f"school_{system}"] = 0
        for start, end in periods:
            days.loc[start:end, f"school_{system}"] = 1

    # тип дня: праздники — подряд идущие выходные, среди которых есть праздник в будни
    off = days["day_off"] == 1
    off_run = (off != off.shift()).cumsum()
    in_holidays = off & (days.groupby(off_run)["holiday"].transform("max") == 1)
    before_holidays = ~off & in_holidays.shift(-1, fill_value=False)
    after_holidays = ~off & in_holidays.shift(1, fill_value=False)
    days["day_type"] = np.select(
        [after_holidays, before_holidays, days["holiday"] == 1, days["work_weekend"] == 1,
         days["dow"] == 5, days["dow"] == 6],
        [6, 5, 3, 4, 1, 2],
        default=0,  # обычный будний день
    )
    return days
