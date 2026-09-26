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