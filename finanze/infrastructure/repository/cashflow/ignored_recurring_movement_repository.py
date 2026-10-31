from datetime import datetime
from uuid import UUID, uuid4

from application.ports.ignored_recurring_movement_port import (
    IgnoredRecurringMovementPort,
)
from dateutil.tz import tzlocal
from domain.cashflow import IgnoredRecurringMovement
from domain.dezimal import Dezimal
from domain.transactions import TxType
from infrastructure.repository.cashflow.queries import IgnoredRecurringMovementQueries
from infrastructure.repository.db.client import DBClient


class IgnoredRecurringMovementRepository(IgnoredRecurringMovementPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_all(self) -> list[IgnoredRecurringMovement]:
        async with self._db_client.read() as cursor:
            await cursor.execute(IgnoredRecurringMovementQueries.GET_ALL)
            return [
                IgnoredRecurringMovement(
                    id=UUID(row["id"]),
                    key=row["key"],
                    type=TxType(row["type"]),
                    currency=row["currency"],
                    amount=Dezimal(row["amount"]),
                )
                for row in await cursor.fetchall()
            ]

    async def save(
        self, movement: IgnoredRecurringMovement
    ) -> IgnoredRecurringMovement:
        if movement.id is None:
            movement.id = uuid4()
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                IgnoredRecurringMovementQueries.INSERT,
                (
                    str(movement.id),
                    movement.key,
                    movement.type.value,
                    movement.currency,
                    str(movement.amount),
                    datetime.now(tzlocal()).isoformat(),
                ),
            )
        return movement

    async def delete(self, ignored_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                IgnoredRecurringMovementQueries.DELETE, (str(ignored_id),)
            )
