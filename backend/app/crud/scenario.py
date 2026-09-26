from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scenario


class ScenarioCRUD:
    async def list(
        self,
        session: AsyncSession,
        active: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Scenario]:
        statement = select(Scenario).order_by(Scenario.date_from, Scenario.id)
        if active is not None:
            statement = statement.where(Scenario.active == active)
        if date_from is not None:
            statement = statement.where(Scenario.date_to >= date_from)
        if date_to is not None:
            statement = statement.where(Scenario.date_from <= date_to)
        result = await session.scalars(statement)
        return list(result.all())

    async def get(self, session: AsyncSession, scenario_id: int) -> Scenario | None:
        return await session.get(Scenario, scenario_id)

    async def create(
        self, session: AsyncSession, scenario: Scenario
    ) -> Scenario:
        session.add(scenario)
        await session.flush()
        return scenario

    async def delete(self, session: AsyncSession, scenario: Scenario) -> None:
        await session.delete(scenario)