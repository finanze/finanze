from typing import Optional
from uuid import UUID, uuid4

from application.ports.periodic_flow_port import PeriodicFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType, PeriodicFlow
from infrastructure.repository.db.client import DBClient


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

    def save(self, flow: PeriodicFlow) -> PeriodicFlow:
        if flow.id is None:
            flow.id = uuid4()

        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                INSERT INTO periodic_flows (id, name, amount, currency, flow_type, frequency, category, enabled, since, until, icon, max_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    flow.icon,
                    str(flow.max_amount) if flow.max_amount else None,
                ),
            )
        return flow

    def update(self, flow: PeriodicFlow):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE periodic_flows 
                SET name = ?, amount = ?, currency = ?, flow_type = ?, frequency = ?, category = ?, enabled = ?, since = ?, until = ?, icon = ?, max_amount = ?
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
                    flow.icon,
                    str(flow.max_amount) if flow.max_amount else None,
                    str(flow.id),
                ),
            )

    def delete(self, flow_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute("DELETE FROM periodic_flows WHERE id = ?", (str(flow_id),))

    def get_all(self) -> list[PeriodicFlow]:
        with self._db_client.read() as cursor:
            cursor.execute("""
                           SELECT f.*, rf.real_estate_id IS NOT NULL AS linked
                           FROM periodic_flows f LEFT JOIN real_estate_flows rf ON f.id = rf.periodic_flow_id
                           """)
            return [_map_row_to_periodic_flow(row) for row in cursor.fetchall()]

    def get_by_id(self, flow_id: UUID) -> Optional[PeriodicFlow]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT f.*, rf.real_estate_id IS NOT NULL AS linked
                FROM periodic_flows f
                         LEFT JOIN real_estate_flows rf ON f.id = rf.periodic_flow_id
                WHERE id = ?
                """,
                (str(flow_id),),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            return _map_row_to_periodic_flow(row)
