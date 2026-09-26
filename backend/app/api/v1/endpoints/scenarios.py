from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import RequireRole
from app.auth.schemas import CurrentUser
from app.crud import ScenarioCRUD
from app.dependencies import get_db_session
from app.dependencies.scenario import get_scenario_crud
from app.enums import Role
from app.models import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioRead, ScenarioUpdate

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


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
) -> ScenarioRead:
    scenario = Scenario(
        **payload.model_dump(exclude={"source_url"}),
        source_url=str(payload.source_url) if payload.source_url else None,
        created_by=current_user.id,
    )
    return ScenarioRead.from_model(await crud.create(session, scenario))


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
) -> ScenarioRead:
    scenario = await crud.get(session, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)
    await session.flush()
    return ScenarioRead.from_model(scenario)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: int,
    _current_user: CurrentUser = Depends(RequireRole(Role.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
    crud: ScenarioCRUD = Depends(get_scenario_crud),
) -> None:
    scenario = await crud.get(session, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    await crud.delete(session, scenario)