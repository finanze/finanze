from uuid import UUID, uuid4

from application.ports.pending_flow_port import PendingFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowType, PendingFlow
from infrastructure.repository.db.client import DBClient


class PendingFlowRepository(PendingFlowPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, flows: list[PendingFlow]):
        with self._db_client.tx() as cursor:
            for flow in flows:
                if flow.id is None:
                    flow.id = uuid4()

                cursor.execute(
                    """
                    INSERT INTO pending_flows (id, name, amount, currency, flow_type, category, enabled, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(flow.id),
                        flow.name,
                        str(flow.amount),
                        flow.currency,
                        flow.flow_type.value,
                        flow.category,
                        flow.enabled,
                        flow.date,
                    ),
                )

    def delete_all(self):
        with self._db_client.tx() as cursor:
            cursor.execute("DELETE FROM pending_flows")

    def get_all(self) -> list[PendingFlow]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM pending_flows")
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
                )
                for row in cursor.fetchall()
            ]
