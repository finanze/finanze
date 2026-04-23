from uuid import UUID, uuid4

from application.ports.pending_flow_port import PendingFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowType, PendingFlow
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.earnings_expenses.queries import PendingFlowsQueries


class PendingFlowRepository(PendingFlowPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, flows: list[PendingFlow]):
        async with self._db_client.tx() as cursor:
            for flow in flows:
                if flow.id is None:
                    flow.id = uuid4()

                await cursor.execute(
                    PendingFlowsQueries.INSERT,
                    (
                        str(flow.id),
                        flow.name,
                        str(flow.amount),
                        flow.currency,
                        flow.flow_type.value,
                        flow.category,
                        flow.enabled,
                        flow.date,
                        flow.icon,
                    ),
                )

    async def delete_all(self):
        async with self._db_client.tx() as cursor:
            await cursor.execute(PendingFlowsQueries.DELETE_ALL)

    async def get_all(self) -> list[PendingFlow]:
        async with self._db_client.read() as cursor:
            await cursor.execute(PendingFlowsQueries.GET_ALL)
            return [
                PendingFlow(
                    id=UUID(row["id"]),
                    name=row["name"],
                    amount=Dezimal(row["amount"]),
                    currency=row["currency"],
                    flow_type=FlowType(row["flow_type"]),
                    category=row["category"],
                    enabled=row["enabled"],
                    date=row["date"],
                    icon=row["icon"],
                )
                for row in await cursor.fetchall()
            ]
