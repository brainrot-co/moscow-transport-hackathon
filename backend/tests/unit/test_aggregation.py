from datetime import datetime

from app.ml.aggregation import aggregate_rows
from app.ml.models import ResponseRow


def row(hour: int, source: str, value: int | None, yhat: float | None) -> ResponseRow:
    return ResponseRow(
        route=7,
        ts=datetime(2026, 10, 1, hour),
        source=source,  # type: ignore[arg-type]
        value=value,
        yhat_model=yhat,
        yhat=yhat,
        q10=None,
        q90=None,
    )


def test_day_aggregation_preserves_actual_semantics():
    result = aggregate_rows(
        [row(10, "actual", 100, None), row(11, "actual", 120, None)],
        "day",
    )

    assert result[0].source == "actual"
    assert result[0].value == 220
    assert result[0].yhat is None


def test_mixed_day_exposes_actual_and_forecast_parts_separately():
    result = aggregate_rows(
        [row(10, "actual", 100, None), row(11, "forecast", None, 200)],
        "day",
    )

    assert result[0].source == "mixed"
    assert result[0].value == 100
    assert result[0].yhat_model == 200
    assert result[0].yhat == 200


def test_day_aggregation_preserves_cold_start_availability():
    unavailable = ResponseRow(
        route=5,
        ts=datetime(2026, 10, 1, 10),
        source=None,
        value=None,
        yhat_model=None,
        yhat=None,
        q10=None,
        q90=None,
        availability="cold_start",
    )

    result = aggregate_rows([unavailable], "day")

    assert result[0].source is None
    assert result[0].availability == "cold_start"


def test_day_aggregation_preserves_zero_after_route_closure():
    closed = row(10, "forecast", None, 0)

    result = aggregate_rows([closed], "day")

    assert result[0].source == "forecast"
    assert result[0].yhat == 0
