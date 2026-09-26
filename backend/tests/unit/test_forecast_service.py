from datetime import date, datetime

from app.ml.models import ActualRecord, ForecastRecord, ForecastSnapshot, RunMetadata
from app.services.forecast import ForecastService, as_api_rows


def snapshot() -> ForecastSnapshot:
    first = datetime(2026, 10, 1, 10)
    second = datetime(2026, 10, 1, 11)
    meta = RunMetadata(
        run_id="run-1",
        kind="short",
        schema_version=1,
        data_cutoff=date(2026, 9, 30),
        step="hour",
        routes=frozenset({7}),
    )
    return ForecastSnapshot(
        actuals={(7, first): ActualRecord(7, first, 120)},
        short={(7, second): ForecastRecord(7, second, 200)},
        year={},
        short_meta=meta,
        watermark=date(2026, 9, 30),
    )


def test_hourly_service_returns_contract_rows():
    service = ForecastService(snapshot())

    rows = service.hourly(
        datetime(2026, 10, 1, 10),
        datetime(2026, 10, 1, 11),
        routes=[7],
    )
    api_rows = as_api_rows(rows)

    assert len(api_rows) == 2
    assert api_rows[0]["source"] is None
    assert api_rows[0]["availability"] == "unavailable"
    assert api_rows[1]["source"] == "forecast"
    assert api_rows[1]["value"] is None
    assert api_rows[1]["yhat_model"] == 200


def test_meta_reports_active_run_and_cutoff():
    meta = ForecastService(snapshot()).meta()

    assert meta["available"] is True
    assert meta["short_run_id"] == "run-1"
    assert meta["data_cutoff"] == date(2026, 9, 30)