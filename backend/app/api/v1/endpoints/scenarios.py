from datetime import date

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import RequireRole
from app.auth.schemas import CurrentUser
from app.crud import ScenarioCRUD
from app.dependencies import get_db_session
from app.dependencies.forecast import get_forecast_store
from app.dependencies.redis import get_redis_client
from app.dependencies.scenario import get_scenario_crud
from app.enums import Role
from app.ml import ForecastStore
from app.models import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioRead, ScenarioUpdate
from app.services.scenario_version import bump_version

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


def _check_reference(
    store: ForecastStore,
    kind: str,
    factor: str,
    value: float,
    routes: list[int] | None,
    check_scope: bool = True,
) -> None:
    # пока воркер не опубликовал справочник, сценарии принимаются без проверки
    if store.correction_factors is None:
        return
    error = store.correction_factors.validate_scenario(
        kind, factor, value, routes, check_scope
    )
    if error is not None:
        raise HTTPException(status_code=422, detail=error)


@router.get("", response_model=list[ScenarioRead])
async def list_scenarios(
    active: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    session: AsyncSession = Depends(get_db_session),
    crud: ScenarioCRUD = Depends(get_scenario_crud),
) -> list[ScenarioRead]:
    scenarios = await crud.list(session, active, date_from, date_to)
    return [ScenarioRead.from_model(scenario) for scenario in scenarios]


@router.post("", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: ScenarioCreate,
    current_user: CurrentUser = Depends(RequireRole(Role.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
    crud: ScenarioCRUD = Depends(get_scenario_crud),
    store: ForecastStore = Depends(get_forecast_store),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> ScenarioRead:
    _check_reference(store, payload.kind, payload.factor, payload.value, payload.routes)
    scenario = Scenario(
        **payload.model_dump(exclude={"source_url"}),
        source_url=str(payload.source_url) if payload.source_url else None,
        created_by=current_user.id,
    )
    created = await crud.create(session, scenario)
    await _commit_and_bump(session, redis_client)
    return ScenarioRead.from_model(created)


@router.get("/{scenario_id}", response_model=ScenarioRead)
async def get_scenario(
    scenario_id: int,
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    session: AsyncSession = Depends(get_db_session),
    crud: ScenarioCRUD = Depends(get_scenario_crud),
) -> ScenarioRead:
    scenario = await crud.get(session, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    return ScenarioRead.from_model(scenario)


@router.patch("/{scenario_id}", response_model=ScenarioRead)
async def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    _current_user: CurrentUser = Depends(RequireRole(Role.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
    crud: ScenarioCRUD = Depends(get_scenario_crud),
    store: ForecastStore = Depends(get_forecast_store),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> ScenarioRead:
    scenario = await crud.get(session, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    value = payload.value if payload.value is not None else scenario.value
    # маршруты PATCH не меняет: старые сценарии с другой областью действия
    # можно править и выключать
    _check_reference(
        store, scenario.kind, scenario.factor, value, scenario.routes, check_scope=False
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)
    await session.flush()
    await _commit_and_bump(session, redis_client)
    return ScenarioRead.from_model(scenario)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: int,
    _current_user: CurrentUser = Depends(RequireRole(Role.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
    crud: ScenarioCRUD = Depends(get_scenario_crud),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> None:
    scenario = await crud.get(session, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    await crud.delete(session, scenario)
    await _commit_and_bump(session, redis_client)


async def _commit_and_bump(session: AsyncSession, redis_client: redis.Redis) -> None:
    # версия растёт только после коммита: иначе соседний воркер успеет закэшировать
    # старые поправки уже под новой версией
    await session.commit()
    await bump_version(redis_client)
