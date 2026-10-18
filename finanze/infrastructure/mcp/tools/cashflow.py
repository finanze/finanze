from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID

from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from domain.cashflow import (
    CashflowGranularity,
    CashflowQuery,
    DEFAULT_RECURRING_LOOKBACK_MONTHS,
    IgnoredRecurringMovement,
    MAX_RECURRING_LOOKBACK_MONTHS,
    RecurringMovementsQuery,
)
from domain.dezimal import Dezimal
from domain.transactions import TxType
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.tools.common import (
    CurrencyCode,
    EntityIds,
    FromDate,
    ToDate,
    resolve_currency,
)
from infrastructure.mcp.use_cases import McpUseCases

MAX_CASHFLOW_RANGE_DAYS = 3660

MovementType = Literal["INFLOW", "OUTFLOW"]


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("Get cashflow")
    async def get_cashflow(
        from_date: FromDate = None,
        to_date: ToDate = None,
        currency: CurrencyCode = None,
        entities: EntityIds = None,
        granularity: CashflowGranularity = CashflowGranularity.MONTH,
    ):
        """Get income vs expenses from account movements: totals with savings rate, comparison with the previous period, series per period, breakdown by label (see list_labels), top counterparties and budget. Defaults to the last 12 months. Movements under EXCLUDED labels are not counted."""
        today = datetime.now(tzlocal()).date()
        end = to_date or today
        start = from_date or (end - relativedelta(months=12) + relativedelta(days=1))
        if start > end:
            raise ToolError("from_date must be before or equal to to_date.")
        if (end - start).days > MAX_CASHFLOW_RANGE_DAYS:
            raise ToolError("Date range is too large, max 10 years.")
        return await ucs.get_cashflow_summary.execute(
            CashflowQuery(
                currency=await resolve_currency(ucs, currency),
                from_date=start,
                to_date=end,
                entities=entities,
                granularity=granularity,
            )
        )

    @registry.read("Get recurring movements")
    async def get_recurring_movements(
        currency: CurrencyCode = None,
        lookback_months: Annotated[
            int, Field(ge=1, le=MAX_RECURRING_LOOKBACK_MONTHS)
        ] = DEFAULT_RECURRING_LOOKBACK_MONTHS,
        entities: EntityIds = None,
        type: Optional[MovementType] = None,
    ):
        """Detect recurring account movements (subscriptions, salaries, bills) from history, with frequency, typical amount, next expected date and whether they are already tracked as periodic flows or ignored."""
        return await ucs.get_recurring_movements.execute(
            RecurringMovementsQuery(
                currency=await resolve_currency(ucs, currency),
                lookback_months=lookback_months,
                entities=entities,
                type=TxType(type) if type else None,
            )
        )

    @registry.write("Ignore recurring movement", idempotent=True)
    async def ignore_recurring_movement(
        key: Annotated[
            str, Field(min_length=1, description="Key from get_recurring_movements.")
        ],
        type: MovementType,
        currency: Annotated[str, Field(min_length=3, max_length=3)],
        amount: Annotated[Decimal, Field(gt=0)],
    ):
        """Hide a detected recurring movement from future detections. Use the values returned by get_recurring_movements."""
        return await ucs.ignore_recurring_movement.execute(
            IgnoredRecurringMovement(
                key=key.strip(),
                type=TxType(type),
                currency=currency.upper(),
                amount=Dezimal(amount),
            )
        )

    @registry.write("Restore recurring movement", idempotent=True)
    async def restore_recurring_movement(
        ignored_id: Annotated[
            UUID, Field(description="ignored_id from get_recurring_movements.")
        ],
    ):
        """Stop ignoring a previously ignored recurring movement."""
        await ucs.restore_recurring_movement.execute(ignored_id)
        return {"restored": str(ignored_id)}
