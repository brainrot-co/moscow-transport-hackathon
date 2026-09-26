from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import RequireRole
from app.auth.schemas import CurrentUser
from app.core import Settings, get_settings
from app.crud import ScenarioCRUD
from app.dependencies import get_db_session
from app.dependencies.forecast import get_forecast_store
from app.dependencies.scenario import get_scenario_crud
from app.enums import Role
from app.ml import ForecastStore
from app.ml.corrections import Scenario as CorrectionScenario
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
    settings: Settings = Depends(get_settings),
) -> ForecastMetaRead:
    return ForecastMetaRead.model_validate(
        ForecastService(store.snapshot).meta(
            error=store.last_error,
            now=store.now(),
            published_at=store.published_at,
            stale_after_days=settings.stale_after_days,
        )
    )


@router.get("", response_model=ForecastResponse)
async def forecast(
    date_from: datetime,
    date_to: datetime,
    routes: list[int] | None = Query(default=None),
    granularity: str = Query(default="hour"),
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
    session: AsyncSession = Depends(get_db_session),
    scenario_crud: ScenarioCRUD = Depends(get_scenario_crud),
    settings: Settings = Depends(get_settings),
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
    model_factors, scenarios = await _saved_corrections(
        session, scenario_crud, date_from, date_to
    )
    service = ForecastService(store.snapshot)
    rows = service.hourly(
        date_from,
        date_to,
        routes,
        model_factors=model_factors,
        scenarios=scenarios,
        granularity=granularity,  # type: ignore[arg-type]
    )
    meta = ForecastMetaRead.model_validate(
        service.meta(
            now=store.now(),
            published_at=store.published_at,
            stale_after_days=settings.stale_after_days,
        )
    )
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
    settings: Settings = Depends(get_settings),
) -> ForecastResponse:
    if payload.date_to < payload.date_from:
        raise HTTPException(
            status_code=422,
            detail="date_to must not precede date_from",
        )
    if store.snapshot is None:
        raise HTTPException(status_code=503, detail="forecast_unavailable")
    scenarios = [
        CorrectionScenario(
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
        granularity=payload.granularity,
    )
    return ForecastResponse(
        query=ForecastQueryRead(
            date_from=payload.date_from,
            date_to=payload.date_to,
            granularity=payload.granularity,
        ),
        data=[ForecastRowRead.model_validate(row) for row in as_api_rows(rows)],
        meta=ForecastMetaRead.model_validate(
            service.meta(
                now=store.now(),
                published_at=store.published_at,
                stale_after_days=settings.stale_after_days,
            )
        ),
    )


async def _saved_corrections(
    session: AsyncSession,
    crud: ScenarioCRUD,
    date_from: datetime,
    date_to: datetime,
) -> tuple[dict[str, float], list[CorrectionScenario]]:
    stored = await crud.list(
        session,
        active=True,
        date_from=date_from.date(),
        date_to=date_to.date(),
    )
    model_factors: dict[str, float] = {}
    scenarios: list[CorrectionScenario] = []
    for item in stored:
        if item.kind == "model_factor":
            model_factors[item.factor] = item.value
            continue
        scenarios.append(
            CorrectionScenario(
                id=str(item.id),
                kind="scenario",
                factor=item.factor,
                value=item.value,
                routes=frozenset(item.routes) if item.routes else None,
                date_from=item.date_from,
                date_to=item.date_to,
                days=item.days,  # type: ignore[arg-type]
                hour_from=item.hour_from,
                hour_to=item.hour_to,
                title=item.title,
            )
        )
    return model_factors, scenarios
