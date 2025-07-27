from uuid import UUID, uuid4

from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from infrastructure.repository.db.client import DBClient


class PeriodicFlowRepository(PeriodicFlowPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, flow: PeriodicFlow):
        if flow.id is None:
            flow.id = uuid4()

        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO periodic_flows (id, name, amount, currency, flow_type, frequency, category, enabled, since, until)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
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
                ),
            )

    def update(self, flow: PeriodicFlow):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE periodic_flows 
                SET name = ?, amount = ?, currency = ?, flow_type = ?, frequency = ?, category = ?, enabled = ?, since = ?, until = ?
                WHERE id = ?
                """,
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
                    str(flow.id),
                ),
            )

    def delete(self, flow_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute("DELETE FROM periodic_flows WHERE id = ?", (str(flow_id),))

    def get_all(self) -> list[PeriodicFlow]:
        with self._db_client.read() as cursor:
            cursor.execute("SELECT * FROM periodic_flows")
            return [
                PeriodicFlow(
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
                )
                for row in cursor.fetchall()
            ]
