from typing import Optional
from uuid import UUID, uuid4

from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.earnings_expenses.queries import PeriodicFlowsQueries


def _map_row_to_periodic_flow(row) -> PeriodicFlow:
    return PeriodicFlow(
        id=UUID(row["id"]),
        name=row["name"],
        amount=Dezimal(row["amount"]),
        currency=row["currency"],
        flow_type=FlowType(row["flow_type"]),
        frequency=FlowFrequency(row["frequency"]),
        category=row["category"],
        enabled=row["enabled"],
        since=row["since"],
        until=row["until"],
        icon=row["icon"],
        linked=row["linked"],
        max_amount=Dezimal(row["max_amount"]) if row["max_amount"] else None,
    )


class PeriodicFlowRepository(PeriodicFlowPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, flow: PeriodicFlow) -> PeriodicFlow:
        if flow.id is None:
            flow.id = uuid4()

        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PeriodicFlowsQueries.INSERT,
                (
                    str(flow.id),
                    flow.name,
                    str(flow.amount),
                    flow.currency,
                    flow.flow_type.value,
                    flow.frequency.value,
                    flow.category,
                    flow.enabled,
                    flow.since,
                    flow.until,
                    flow.icon,
                    str(flow.max_amount) if flow.max_amount else None,
                ),
            )
        return flow

    async def update(self, flow: PeriodicFlow):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PeriodicFlowsQueries.UPDATE,
                (
                    flow.name,
                    str(flow.amount),
                    flow.currency,
                    flow.flow_type.value,
                    flow.frequency.value,
                    flow.category,
                    flow.enabled,
                    flow.since,
                    flow.until,
                    flow.icon,
                    str(flow.max_amount) if flow.max_amount else None,
                    str(flow.id),
                ),
            )

    async def delete(self, flow_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(PeriodicFlowsQueries.DELETE_BY_ID, (str(flow_id),))

    async def get_all(self) -> list[PeriodicFlow]:
        async with self._db_client.read() as cursor:
            await cursor.execute(PeriodicFlowsQueries.GET_ALL)
            return [_map_row_to_periodic_flow(row) for row in await cursor.fetchall()]

    async def get_by_id(self, flow_id: UUID) -> Optional[PeriodicFlow]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PeriodicFlowsQueries.GET_BY_ID,
                (str(flow_id),),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            return _map_row_to_periodic_flow(row)
