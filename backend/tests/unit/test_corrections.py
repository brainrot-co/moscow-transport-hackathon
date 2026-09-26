import math
from datetime import date, datetime

from app.ml.corrections import Scenario, apply_corrections
from app.ml.models import ResponseRow


def forecast_row() -> ResponseRow:
    return ResponseRow(
        route=7,
        ts=datetime(2026, 10, 1, 10),
        source="forecast",
        value=None,
        yhat_model=100.0,
        yhat=100.0,
        q10=80.0,
        q90=120.0,
    )


def test_actual_is_never_changed_by_corrections():
    actual = ResponseRow(
        route=7,
        ts=datetime(2026, 10, 1, 10),
        source="actual",
        value=120,
        yhat_model=None,
        yhat=None,
        q10=None,
        q90=None,
    )

    result = apply_corrections(
        [actual],
        effects={(7, date(2026, 10, 1), "holiday"): -0.7},
        model_factors={"holiday": 0.0},
        scenarios=[
            Scenario(
                id="closed",
                kind="scenario",
                factor="route_closed",
                value=0.0,
                date_from=date(2026, 10, 1),
                date_to=date(2026, 10, 2),
                routes=frozenset({7}),
            )
        ],
    )

    assert result[0] == actual


def test_model_factor_and_scenario_are_applied_to_forecast():
    result = apply_corrections(
        [forecast_row()],
        effects={(7, date(2026, 10, 1), "holiday"): -0.5},
        model_factors={"holiday": 0.0},
        scenarios=[
            Scenario(
                id="rain",
                kind="scenario",
                factor="heavy_rain",
                value=0.8,
                date_from=date(2026, 10, 1),
                date_to=date(2026, 10, 1),
                routes=frozenset({7}),
            )
        ],
    )

    assert result[0].yhat is not None
    assert round(result[0].yhat, 6) == round(100 * math.exp(0.5) * 0.8, 6)
    assert result[0].q10 is not None
    assert len(result[0].applied) == 2


def test_scenario_respects_weekday_and_hour_scope():
    row = forecast_row()
    scenario = Scenario(
        id="repair",
        kind="scenario",
        factor="route_shortened",
        value=0.7,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 1),
        routes=frozenset({7}),
        days="weekends",
        hour_from=8,
        hour_to=12,
    )

    assert not scenario.applies(row.route, row.ts)