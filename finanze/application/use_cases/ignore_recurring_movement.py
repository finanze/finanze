from application.ports.ignored_recurring_movement_port import (
    IgnoredRecurringMovementPort,
)
from domain.cashflow import IgnoredRecurringMovement
from domain.use_cases.ignore_recurring_movement import IgnoreRecurringMovement


class IgnoreRecurringMovementImpl(IgnoreRecurringMovement):
    def __init__(self, ignored_recurring_movement_port: IgnoredRecurringMovementPort):
        self._ignored_port = ignored_recurring_movement_port

    async def execute(
        self, movement: IgnoredRecurringMovement
    ) -> IgnoredRecurringMovement:
        movement.id = None
        movement.currency = movement.currency.upper()
        return await self._ignored_port.save(movement)
