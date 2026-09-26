from collections.abc import Iterable
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
LABELS_DIR = ROOT / "dataset" / "labels"

ALL_ROUTES = (1, 5, 7, 11, 12, 17, 25, 26, 28, 50)
# маршрута 5 нет в разметке, в сабмишене он всегда 0
ZERO_ROUTES = (5,)
MODEL_ROUTES = tuple(r for r in ALL_ROUTES if r not in ZERO_ROUTES)


def load_labels(paths: Iterable[Path] | None = None):
    """В разметке только часы с посадками: пустые часы добавляет to_hourly_grid."""
    if paths is None:
        paths = [LABELS_DIR / "labels_day_train.csv", LABELS_DIR / "labels_day_test.csv"]
    df = pd.concat([pd.read_csv(p, sep=";") for p in paths], ignore_index=True)
    ts = pd.to_datetime(df["date"]) + pd.to_timedelta(df["hour"], unit="h")
    return pd.DataFrame(
        {"route": df["route"].astype(int), "ts": ts, "y": df["boardings"].astype(float)}
    )


def to_hourly_grid(
    df: pd.DataFrame,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    routes: Iterable[int] = MODEL_ROUTES,
):
    """Пустой час внутри дня = 0; пропущенный день = среднее ближайших дней с тем же днём недели."""
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    index = pd.MultiIndex.from_product([list(routes), hours], names=["route", "ts"])
    grid = df.set_index(["route", "ts"])["y"].reindex(index).fillna(0.0).reset_index()

    observed_days = set(zip(df["route"], df["ts"].dt.normalize(), strict=True))
    grid["day"] = grid["ts"].dt.normalize()
    wide = grid.pivot_table(index=["route", "day"], columns=grid["ts"].dt.hour, values="y")
    days = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    for route in routes:
        for day in days:
            if (route, day) in observed_days:
                continue
            wide.loc[(route, day)] = _same_weekday_fill(wide, observed_days, route, day, days)

    long = wide.stack().rename("y").reset_index()
    long["ts"] = long["day"] + pd.to_timedelta(long["ts"], unit="h")
    return long[["route", "ts", "y"]].sort_values(["route", "ts"], ignore_index=True)


def _same_weekday_fill(
    wide: pd.DataFrame,
    observed: set[tuple[int, pd.Timestamp]],
    route: int,
    day: pd.Timestamp,
    days: pd.DatetimeIndex,
):
    for k in range(1, len(days) // 7 + 1):
        neighbours = [day + pd.Timedelta(days=s * 7 * k) for s in (-1, 1)]
        found = [wide.loc[(route, d)] for d in neighbours if (route, d) in observed]
        if found:
            return pd.concat(found, axis=1).mean(axis=1)
    raise ValueError(f"Нет ни одного дня того же дня недели для маршрута {route}, {day:%Y-%m-%d}")


def load_series(start: str = "2025-01-01", end: str = "2025-10-31"):
    return to_hourly_grid(load_labels(), start, end)
