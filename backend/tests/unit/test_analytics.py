from datetime import date, datetime

from app.ml.load import LoadNormSettings
from app.ml.models import ActualRecord, ForecastRecord, ForecastSnapshot
from app.services.analytics import build_forecast_analytics
from app.services.forecast import ForecastService

SETTINGS = LoadNormSettings(
    weeks=8,
    min_days=2,
    low_quantile=0.25,
    high_quantile=0.75,
    min_deviation=0.1,
)


def test_analytics_aggregates_network_and_route_peaks():
    day = date(2026, 9, 27)
    snapshot = ForecastSnapshot(
        actuals={
            (7, datetime(2026, 9, 27, 8)): ActualRecord(
                7, datetime(2026, 9, 27, 8), 100
            ),
            (17, datetime(2026, 9, 27, 8)): ActualRecord(
                17, datetime(2026, 9, 27, 8), 150
            ),
        },
        short={
            (7, datetime(2026, 9, 27, 9)): ForecastRecord(
                7, datetime(2026, 9, 27, 9), 180
            ),
            (17, datetime(2026, 9, 27, 9)): ForecastRecord(
                17, datetime(2026, 9, 27, 9), 220
            ),
        },
        year={},
        watermark=day,
        daily_actuals={
            7: {
                date(2026, 9, 13): 250,
                date(2026, 9, 20): 300,
            },
            17: {
                date(2026, 9, 13): 350,
                date(2026, 9, 20): 400,
            },
        },
    )

    result = build_forecast_analytics(ForecastService(snapshot), day, [7, 17], SETTINGS)

    assert result.selected_routes == (7, 17)
    assert result.hours[8].actual == 250
    assert result.hours[9].forecast == 400
    assert result.routes[0].total == 280
    assert result.routes[0].peak_hour == 9
    assert result.routes[0].hourly_sources[8] == "actual"
    assert result.routes[0].hourly_sources[9] == "forecast"
    assert result.routes[1].peak_value == 220


def test_analytics_preserves_unavailable_hours():
    day = date(2026, 9, 27)
    snapshot = ForecastSnapshot(actuals={}, short={}, year={})

    result = build_forecast_analytics(ForecastService(snapshot), day, [7], SETTINGS)

    assert result.selected_routes == (7,)
    assert result.hours[12].total is None
    assert result.routes[0].hourly == (None,) * 24
