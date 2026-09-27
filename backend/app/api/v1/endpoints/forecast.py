from datetime import date, datetime, time

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
from app.ml.load import LoadNormSettings
from app.schemas.forecast import (
    AnalyticsHourRead,
    AnalyticsRouteRead,
    ForecastAnalyticsResponse,
    ForecastMetaRead,
    ForecastPreviewRequest,
    ForecastQueryRead,
    ForecastResponse,
    ForecastRowRead,
    RouteLoadRead,
    RouteLoadResponse,
)
from app.services.analytics import build_forecast_analytics
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


@router.get("/load", response_model=RouteLoadResponse)
async def route_load(
    day: date | None = Query(default=None, alias="date"),
    routes: list[int] | None = Query(default=None),
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
    session: AsyncSession = Depends(get_db_session),
    scenario_crud: ScenarioCRUD = Depends(get_scenario_crud),
    settings: Settings = Depends(get_settings),
) -> RouteLoadResponse:
    if store.snapshot is None:
        raise HTTPException(status_code=503, detail="forecast_unavailable")
    day = day or store.now().date()
    model_factors, scenarios = await _saved_corrections(
        session,
        scenario_crud,
        datetime.combine(day, time()),
        datetime.combine(day, time(23)),
    )
    service = ForecastService(store.snapshot)
    loads = service.route_loads(
        day,
        routes,
        LoadNormSettings(
            weeks=settings.load_norm_weeks,
            min_days=settings.load_norm_min_days,
            low_quantile=settings.load_low_quantile,
            high_quantile=settings.load_high_quantile,
            min_deviation=settings.load_min_deviation,
        ),
        model_factors=model_factors,
        scenarios=scenarios,
    )
    return RouteLoadResponse(
        date=day,
        day_kind=service.day_kind(day),
        day_type=store.snapshot.day_types.get(day),
        norm_weeks=settings.load_norm_weeks,
        low_quantile=settings.load_low_quantile,
        high_quantile=settings.load_high_quantile,
        min_deviation=settings.load_min_deviation,
        data=[
            RouteLoadRead(
                route=load.route,
                value=load.value,
                load_level=load.level,
                ratio=(
                    load.value / load.norm.median
                    if load.norm and load.value is not None and load.norm.median > 0
                    else None
                ),
                norm_low=load.norm.low if load.norm else None,
                norm_median=load.norm.median if load.norm else None,
                norm_high=load.norm.high if load.norm else None,
                norm_days=load.norm.days if load.norm else 0,
                norm_from=load.norm.date_from if load.norm else None,
                norm_to=load.norm.date_to if load.norm else None,
            )
            for load in loads
        ],
        meta=ForecastMetaRead.model_validate(
            service.meta(
                now=store.now(),
                published_at=store.published_at,
                stale_after_days=settings.stale_after_days,
            )
        ),
    )


@router.get("/analytics", response_model=ForecastAnalyticsResponse)
async def forecast_analytics(
    day: date | None = Query(default=None, alias="date"),
    routes: list[int] | None = Query(default=None),
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
    session: AsyncSession = Depends(get_db_session),
    scenario_crud: ScenarioCRUD = Depends(get_scenario_crud),
    settings: Settings = Depends(get_settings),
):
    if store.snapshot is None:
        raise HTTPException(status_code=503, detail="forecast_unavailable")
    day = day or store.now().date()
    model_factors, scenarios = await _saved_corrections(
        session,
        scenario_crud,
        datetime.combine(day, time()),
        datetime.combine(day, time(23)),
    )
    service = ForecastService(store.snapshot)
    result = build_forecast_analytics(
        service,
        day,
        routes,
        LoadNormSettings(
            weeks=settings.load_norm_weeks,
            min_days=settings.load_norm_min_days,
            low_quantile=settings.load_low_quantile,
            high_quantile=settings.load_high_quantile,
            min_deviation=settings.load_min_deviation,
        ),
        model_factors=model_factors,
        scenarios=scenarios,
    )
    return ForecastAnalyticsResponse(
        date=result.day,
        selected_routes=result.selected_routes,
        norm_weeks=settings.load_norm_weeks,
        norm_min_days=settings.load_norm_min_days,
        hours=tuple(
            AnalyticsHourRead(
                ts=point.ts,
                actual=point.actual,
                forecast=point.forecast,
                total=point.total,
                available_routes=point.available_routes,
                total_routes=point.total_routes,
            )
            for point in result.hours
        ),
        routes=tuple(
            AnalyticsRouteRead(
                route=route.route,
                hourly=route.hourly,
                hourly_sources=route.hourly_sources,
                actual=route.actual,
                forecast=route.forecast,
                total=route.total,
                peak_hour=route.peak_hour,
                peak_value=route.peak_value,
                ratio=route.ratio,
                deviation_percent=route.deviation_percent,
                load_level=route.load_level,
                norm_median=route.norm_median,
                norm_days=route.norm_days,
            )
            for route in result.routes
        ),
        meta=ForecastMetaRead.model_validate(
            service.meta(
                now=store.now(),
                published_at=store.published_at,
                stale_after_days=settings.stale_after_days,
            )
        ),
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
