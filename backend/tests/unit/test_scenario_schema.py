from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.scenario import ScenarioCreate


def test_scenario_schema_accepts_scoped_weekday_event():
    scenario = ScenarioCreate(
        kind="scenario",
        factor="route_shortened",
        value=0.7,
        routes=[7],
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 5),
        days="weekdays",
        hour_from=8,
        hour_to=20,
        title="Repair",
    )

    assert scenario.routes == [7]
    assert scenario.value == 0.7


@pytest.mark.parametrize(
    "payload",
    [
        {"date_from": date(2026, 10, 5), "date_to": date(2026, 10, 1)},
        {
            "date_from": date(2026, 10, 1),
            "date_to": date(2026, 10, 5),
            "hour_from": 20,
            "hour_to": 8,
        },
    ],
)
def test_scenario_schema_rejects_reverse_ranges(payload):
    with pytest.raises(ValidationError):
        ScenarioCreate(kind="scenario", factor="rain", value=0.9, **payload)


def test_model_factor_cannot_target_specific_routes():
    with pytest.raises(ValidationError, match="city scope"):
        ScenarioCreate(
            kind="model_factor",
            factor="holiday",
            value=1.0,
            routes=[7],
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 1),
        )