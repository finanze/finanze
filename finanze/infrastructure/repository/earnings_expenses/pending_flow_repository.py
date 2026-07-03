from typing import Optional
from uuid import UUID, uuid4

from application.ports.pending_flow_port import PendingFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowStatus, FlowType, PendingFlow
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.earnings_expenses.queries import PendingFlowsQueries


def _map_row_to_pending_flow(row) -> PendingFlow:
    return PendingFlow(
        id=UUID(row["id"]),
        name=row["name"],
        amount=Dezimal(row["amount"]),
        currency=row["currency"],
        flow_type=FlowType(row["flow_type"]),
        category=row["category"],
        status=FlowStatus(row["status"]),
        date=row["date"],
        icon=row["icon"],
        status_changed_at=row["status_changed_at"],
    )


class PendingFlowRepository(PendingFlowPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, flow: PendingFlow) -> PendingFlow:
        if flow.id is None:
            flow.id = uuid4()

        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PendingFlowsQueries.INSERT,
                (
                    str(flow.id),
                    flow.name,
                    str(flow.amount),
                    flow.currency,
                    flow.flow_type.value,
                    flow.category,
                    flow.status.value,
                    flow.status_changed_at.isoformat()
                    if flow.status_changed_at
                    else None,
                    flow.date,
                    flow.icon,
                ),
            )
        return flow

    async def update(self, flow: PendingFlow):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PendingFlowsQueries.UPDATE,
                (
                    flow.name,
                    str(flow.amount),
                    flow.currency,
                    flow.flow_type.value,
                    flow.category,
                    flow.status.value,
                    flow.status_changed_at.isoformat()
                    if flow.status_changed_at
                    else None,
                    flow.date,
                    flow.icon,
                    str(flow.id),
                ),
            )

    async def delete(self, flow_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(PendingFlowsQueries.DELETE_BY_ID, (str(flow_id),))

    async def get_all(self) -> list[PendingFlow]:
        async with self._db_client.read() as cursor:
            await cursor.execute(PendingFlowsQueries.GET_ALL)
            return [_map_row_to_pending_flow(row) for row in await cursor.fetchall()]

    async def get_by_id(self, flow_id: UUID) -> Optional[PendingFlow]:
        async with self._db_client.read() as cursor:
            await cursor.execute(PendingFlowsQueries.GET_BY_ID, (str(flow_id),))
            row = await cursor.fetchone()
            if row is None:
                return None
            return _map_row_to_pending_flow(row)
