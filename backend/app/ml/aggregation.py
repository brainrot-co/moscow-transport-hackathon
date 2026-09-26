from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

from .models import ResponseRow

Granularity = Literal["hour", "day", "week", "month"]


def aggregate_rows(
    rows: list[ResponseRow], granularity: Granularity
) -> list[ResponseRow]:
    if granularity == "hour":
        return rows

    grouped: dict[tuple[int, datetime], list[ResponseRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.route, _bucket(row.ts, granularity))].append(row)

    result: list[ResponseRow] = []
    for (route, timestamp), bucket in sorted(grouped.items()):
        actuals = [row for row in bucket if row.source == "actual"]
        forecasts = [
            row
            for row in bucket
            if row.source in {"forecast", "forecast_seasonal"}
        ]
        unavailable = [row for row in bucket if row.source is None]
        yhat_model = (
            sum(row.yhat_model or 0 for row in forecasts) if forecasts else None
        )
        yhat = sum(row.yhat or 0 for row in forecasts) if forecasts else None
        # Forecast quantiles are not additive. Aggregated intervals require a
        # separate estimate, so the public contract intentionally returns null.
        q10 = None
        q90 = None
        if actuals and not forecasts and not unavailable:
            source = "actual"
        elif forecasts and not actuals and not unavailable:
            source = (
                "forecast"
                if all(row.source == "forecast" for row in forecasts)
                else "forecast_seasonal"
            )
        elif actuals or forecasts:
            source = "mixed"
        else:
            source = None
        result.append(
            ResponseRow(
                route=route,
                ts=timestamp,
                source=source,
                value=sum(row.value or 0 for row in actuals) if actuals else None,
                yhat_model=yhat_model,
                yhat=yhat,
                q10=q10,
                q90=q90,
                estimated=any(row.estimated for row in bucket),
                applied=tuple(item for row in bucket for item in row.applied),
                availability=(
                    (
                        "cold_start"
                        if any(row.availability == "cold_start" for row in unavailable)
                        else "unavailable"
                    )
                    if unavailable and not actuals and not forecasts
                    else None
                ),
            )
        )
    return result


def _bucket(timestamp: datetime, granularity: Granularity) -> datetime:
    if granularity == "day":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        start = timestamp - timedelta(days=timestamp.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
