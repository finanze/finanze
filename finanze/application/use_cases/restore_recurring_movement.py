from uuid import UUID

from application.ports.ignored_recurring_movement_port import (
    IgnoredRecurringMovementPort,
)
from domain.use_cases.restore_recurring_movement import RestoreRecurringMovement


class RestoreRecurringMovementImpl(RestoreRecurringMovement):
    def __init__(self, ignored_recurring_movement_port: IgnoredRecurringMovementPort):
        self._ignored_port = ignored_recurring_movement_port

    async def execute(self, ignored_id: UUID):
        await self._ignored_port.delete(ignored_id)
