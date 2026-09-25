from datetime import date

import numpy as np
import pandas as pd

from mtml.ingest.settings import IngestSettings

# ожидаемый объём дня — медиана того же дня недели за столько предыдущих недель
EXPECTED_WEEKS = 4


def day_status(actuals: pd.DataFrame, today: date, settings: IngestSettings):
    """[route, date, status, observed, expected, anomaly] за все дни от первых данных до today."""
    daily = actuals.groupby(["route", actuals["ts"].dt.normalize().rename("date")])[
        "boardings"
    ].sum()
    routes = sorted(set(settings.routes) | set(actuals["route"]))
    dates = pd.date_range(daily.index.get_level_values("date").min(), pd.Timestamp(today))
    observed = daily.unstack("route").reindex(index=dates, columns=routes)
    expected = (
        pd.concat([observed.shift(7 * week) for week in range(1, EXPECTED_WEEKS + 1)])
        .groupby(level=0)
        .median()
        .reindex(index=dates, columns=routes)
    )
    age = pd.DataFrame(
        np.repeat((pd.Timestamp(today) - dates).days.to_numpy()[:, None], len(routes), axis=1),
        index=dates,
        columns=routes,
    )
    has_data = observed.notna()
    matured = age >= settings.finalize_after_days
    # досрочно полным считается только вчерашний и более ранний день, набравший почти весь объём
    early = has_data & (age >= 1) & (observed >= settings.completeness_ratio * expected)
    status = np.select(
        [has_data & (matured | early), ~has_data & matured], ["final", "missing"], "partial"
    )
    # низкий объём — это флаг для лога и интерфейса, а не понижение статуса: ремонт на
    # маршруте даёт настоящие почти пустые дни, и выкидывать их из контекста нельзя
    anomaly = has_data & (observed < settings.anomaly_ratio * expected)

    frame = pd.DataFrame(
        {
            "status": pd.DataFrame(status, index=dates, columns=routes).stack(),
            "observed": observed.fillna(0).stack(),
            "expected": expected.stack(),
            "anomaly": anomaly.stack(),
        }
    )
    frame.index.names = ["date", "route"]
    return (
        frame.reset_index()
        .astype({"route": "int16", "observed": "int32"})
        .sort_values(["route", "date"], ignore_index=True)[
            ["route", "date", "status", "observed", "expected", "anomaly"]
        ]
    )


def watermark(status: pd.DataFrame):
    """Последний день, до которого нет partial ни у одного маршрута и есть хотя бы один final."""
    partial = status.loc[status["status"] == "partial", "date"]
    final = status.loc[status["status"] == "final", "date"]
    if not partial.empty:
        final = final[final < partial.min()]
    return None if final.empty else final.max().date()
