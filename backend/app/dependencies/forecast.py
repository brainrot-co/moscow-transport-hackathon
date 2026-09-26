from fastapi import Request

from app.ml import ForecastStore


def get_forecast_store(request: Request) -> ForecastStore:
    store = getattr(request.app.state, "forecast_store", None)
    if store is None:
        store = ForecastStore("/data")
        request.app.state.forecast_store = store
    return store