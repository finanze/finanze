from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowFrequency,
    FlowStatus,
    FlowType,
    PendingFlow,
    PendingFlowQuery,
    PeriodicFlow,
    SettlePendingFlowRequest,
)
from domain.exception.exceptions import FlowNotFound
from domain.money_event import MoneyEventQuery
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.tools.common import FromDate, ToDate
from infrastructure.mcp.use_cases import McpUseCases

FlowId = Annotated[UUID, Field(description="Flow ID.")]
OptionalFlowId = Annotated[
    Optional[UUID],
    Field(description="Existing flow ID to update. Omit to create a new flow."),
]
Amount = Annotated[Optional[Decimal], Field(description="Positive amount.", gt=0)]
Currency = Annotated[
    Optional[str],
    Field(description="ISO 4217 currency code.", min_length=3, max_length=3),
]
Category = Annotated[Optional[str], Field(description="Free text category.")]


def _merge(current, **changes):
    return replace(current, **{k: v for k, v in changes.items() if v is not None})


def _require(**fields):
    missing = [name for name, value in fields.items() if value is None]
    if missing:
        raise ToolError(f"Missing required fields: {', '.join(missing)}")


def register(registry: ToolRegistry, ucs: McpUseCases):
    async def find_periodic(flow_id: UUID) -> PeriodicFlow:
        flow = next(
            (f for f in await ucs.get_periodic_flows.execute() if f.id == flow_id),
            None,
        )
        if flow is None:
            raise FlowNotFound()
        return flow

    async def find_pending(flow_id: UUID) -> PendingFlow:
        page = await ucs.query_pending_flows.execute(PendingFlowQuery())
        flow = next((f for f in page.entries if f.id == flow_id), None)
        if flow is None:
            raise FlowNotFound()
        return flow

    @registry.read("List periodic flows")
    async def list_periodic_flows():
        """List recurring earnings and expenses (salary, rent, subscriptions, loan installments...) with amount, frequency, active period, next date and linked label."""
        return await ucs.get_periodic_flows.execute()

    @registry.read("List pending flows")
    async def list_pending_flows(
        statuses: Annotated[
            Optional[list[FlowStatus]],
            Field(description="Filter by status. Omit for all."),
        ] = None,
        flow_type: Optional[FlowType] = None,
    ):
        """List one-off expected earnings or expenses (pending payments or collections) with their status and expected date, including totals by status."""
        return await ucs.query_pending_flows.execute(
            PendingFlowQuery(statuses=statuses, flow_type=flow_type, include_stats=True)
        )

    @registry.read("Get money events")
    async def get_money_events(
        from_date: FromDate = None,
        to_date: ToDate = None,
    ):
        """Get the calendar of upcoming or past money events: periodic and pending flows occurrences, investment maturities, interest and contribution dates. Defaults to the next 3 months."""
        start = from_date or datetime.now(tzlocal()).date()
        end = to_date or start + relativedelta(months=3)
        if end < start:
            raise ToolError("to_date must be after from_date.")
        return await ucs.get_money_events.execute(
            MoneyEventQuery(from_date=start, to_date=end)
        )

    @registry.write("Save periodic flow")
    async def save_periodic_flow(
        flow_id: OptionalFlowId = None,
        name: Annotated[Optional[str], Field(min_length=1)] = None,
        amount: Amount = None,
        currency: Currency = None,
        flow_type: Optional[FlowType] = None,
        frequency: Optional[FlowFrequency] = None,
        since: Annotated[
            Optional[date], Field(description="First occurrence date.")
        ] = None,
        until: Annotated[
            Optional[date], Field(description="Last possible occurrence date.")
        ] = None,
        category: Category = None,
        enabled: Optional[bool] = None,
        max_amount: Annotated[
            Optional[Decimal],
            Field(description="Upper bound for variable amounts (e.g. utility bills)."),
        ] = None,
        label_id: Annotated[
            Optional[UUID], Field(description="Label to link (see list_labels).")
        ] = None,
    ):
        """Create a recurring earning or expense, or update one by flow_id. On update only the provided fields change. On create name, amount, currency, flow_type, frequency and since are required."""
        if flow_id:
            current = await find_periodic(flow_id)
            flow = _merge(
                current,
                name=name,
                amount=Dezimal(amount) if amount is not None else None,
                currency=currency.upper() if currency else None,
                flow_type=flow_type,
                frequency=frequency,
                since=since,
                until=until,
                category=category,
                enabled=enabled,
                max_amount=Dezimal(max_amount) if max_amount is not None else None,
                label_id=label_id,
            )
            await ucs.update_periodic_flow.execute(flow, label_id_provided=True)
            return {"updated": str(flow_id)}

        _require(
            name=name,
            amount=amount,
            currency=currency,
            flow_type=flow_type,
            frequency=frequency,
            since=since,
        )
        flow = PeriodicFlow(
            id=None,
            name=name,
            amount=Dezimal(amount),
            currency=currency.upper(),
            flow_type=flow_type,
            frequency=frequency,
            category=category,
            enabled=True if enabled is None else enabled,
            since=since,
            until=until,
            icon=None,
            max_amount=Dezimal(max_amount) if max_amount is not None else None,
            label_id=label_id,
        )
        await ucs.save_periodic_flow.execute(flow)
        return {"created": str(flow.id)}

    @registry.write("Delete periodic flow", destructive=True, idempotent=True)
    async def delete_periodic_flow(flow_id: FlowId):
        """Delete a recurring earning or expense."""
        await ucs.delete_periodic_flow.execute(flow_id)
        return {"deleted": str(flow_id)}

    @registry.write("Save pending flow")
    async def save_pending_flow(
        flow_id: OptionalFlowId = None,
        name: Annotated[Optional[str], Field(min_length=1)] = None,
        amount: Amount = None,
        currency: Currency = None,
        flow_type: Optional[FlowType] = None,
        expected_date: Annotated[
            Optional[date], Field(description="Expected date.")
        ] = None,
        category: Category = None,
        status: Optional[FlowStatus] = None,
    ):
        """Create a one-off expected earning or expense, or update one by flow_id. On update only the provided fields change. On create name, amount, currency and flow_type are required."""
        if flow_id:
            current = await find_pending(flow_id)
            flow = _merge(
                current,
                name=name,
                amount=Dezimal(amount) if amount is not None else None,
                currency=currency.upper() if currency else None,
                flow_type=flow_type,
                date=expected_date,
                category=category,
                status=status,
            )
            await ucs.update_pending_flow.execute(flow)
            return {"updated": str(flow_id)}

        _require(name=name, amount=amount, currency=currency, flow_type=flow_type)
        flow = PendingFlow(
            id=None,
            name=name,
            amount=Dezimal(amount),
            currency=currency.upper(),
            flow_type=flow_type,
            category=category,
            status=status or FlowStatus.ACTIVE,
            date=expected_date,
            icon=None,
        )
        await ucs.save_pending_flow.execute(flow)
        return {"created": str(flow.id)}

    @registry.write("Delete pending flow", destructive=True, idempotent=True)
    async def delete_pending_flow(flow_id: FlowId):
        """Delete a one-off expected earning or expense."""
        await ucs.delete_pending_flow.execute(flow_id)
        return {"deleted": str(flow_id)}

    @registry.write("Settle pending flow")
    async def settle_pending_flow(
        flow_id: FlowId,
        account_id: Annotated[
            UUID,
            Field(
                description="ID of a manually added account position (see get_positions) that receives or pays it."
            ),
        ],
    ):
        """Mark a pending flow as completed, registering the movement on the given manual account."""
        await ucs.settle_pending_flow.execute(
            SettlePendingFlowRequest(flow_id=flow_id, account_id=account_id)
        )
        return {"settled": str(flow_id)}
