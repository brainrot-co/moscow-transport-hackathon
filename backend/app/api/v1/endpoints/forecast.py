from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.permissions import RequireRole
from app.auth.schemas import CurrentUser
from app.dependencies.forecast import get_forecast_store
from app.enums import Role
from app.ml import ForecastStore
from app.ml.corrections import Scenario
from app.schemas.forecast import (
    ForecastMetaRead,
    ForecastPreviewRequest,
    ForecastQueryRead,
    ForecastResponse,
    ForecastRowRead,
)
from app.services.forecast import ForecastService, as_api_rows

router = APIRouter(prefix="/forecast", tags=["Forecast"])


@router.get("/meta", response_model=ForecastMetaRead)
async def forecast_meta(
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
) -> ForecastMetaRead:
    return ForecastMetaRead.model_validate(
        ForecastService(store.snapshot).meta(error=store.last_error)
    )


@router.get("", response_model=ForecastResponse)
async def forecast(
    date_from: datetime,
    date_to: datetime,
    routes: list[int] | None = Query(default=None),
    granularity: str = Query(default="hour"),
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
) -> ForecastResponse:
    if granularity not in {"hour", "day", "week", "month"}:
        raise HTTPException(
            status_code=422,
            detail="unsupported_granularity",
        )
    if date_to < date_from:
        raise HTTPException(
            status_code=422,
            detail="date_to must not precede date_from",
        )
    if store.snapshot is None:
        raise HTTPException(status_code=503, detail="forecast_unavailable")
    rows = ForecastService(store.snapshot).hourly(
        date_from,
        date_to,
        routes,
        granularity=granularity,  # type: ignore[arg-type]
    )
    meta = ForecastMetaRead.model_validate(ForecastService(store.snapshot).meta())
    return ForecastResponse(
        query=ForecastQueryRead(
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,  # type: ignore[arg-type]
        ),
        data=[ForecastRowRead.model_validate(row) for row in as_api_rows(rows)],
        meta=meta,
    )


@router.post("/preview", response_model=ForecastResponse)
async def forecast_preview(
    payload: ForecastPreviewRequest,
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
) -> ForecastResponse:
    if payload.date_to < payload.date_from:
        raise HTTPException(
            status_code=422,
            detail="date_to must not precede date_from",
        )
    if store.snapshot is None:
        raise HTTPException(status_code=503, detail="forecast_unavailable")
    scenarios = [
        Scenario(
            id=f"draft-{index}",
            kind=scenario.kind,
            factor=scenario.factor,
            value=scenario.value,
            routes=frozenset(scenario.routes) if scenario.routes else None,
            date_from=scenario.date_from,
            date_to=scenario.date_to,
            days=scenario.days,
            hour_from=scenario.hour_from,
            hour_to=scenario.hour_to,
            title=scenario.title,
        )
        for index, scenario in enumerate(payload.draft)
    ]
    service = ForecastService(store.snapshot)
    rows = service.hourly(
        payload.date_from,
        payload.date_to,
        payload.routes,
        model_factors=payload.model_factors,
        scenarios=scenarios,
    )
    return ForecastResponse(
        query=ForecastQueryRead(
            date_from=payload.date_from,
            date_to=payload.date_to,
            granularity="hour",
        ),
        data=[ForecastRowRead.model_validate(row) for row in as_api_rows(rows)],
        meta=ForecastMetaRead.model_validate(service.meta()),
    )