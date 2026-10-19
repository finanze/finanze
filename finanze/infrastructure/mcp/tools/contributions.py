from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from domain.auto_contributions import (
    ContributionFrequency,
    ContributionQueryRequest,
    ContributionTargetSubtype,
    ContributionTargetType,
    ManualPeriodicContribution,
    PeriodicContribution,
)
from domain.dezimal import Dezimal
from domain.fetch_record import DataSource
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

ContributionId = Annotated[
    UUID,
    Field(
        description="Manual contribution ID (see get_contributions with real=false)."
    ),
]

_NO_SUBTYPE = {ContributionTargetType.FUND_PORTFOLIO, ContributionTargetType.CRYPTO}


def _to_manual(
    entity_id: UUID, contribution: PeriodicContribution
) -> ManualPeriodicContribution:
    return ManualPeriodicContribution(
        entity_id=entity_id,
        name=contribution.alias or contribution.target_name,
        target=contribution.target,
        target_name=contribution.target_name,
        target_type=contribution.target_type,
        target_subtype=contribution.target_subtype,
        amount=contribution.amount,
        currency=contribution.currency,
        since=contribution.since,
        until=contribution.until,
        frequency=contribution.frequency,
    )


def _normalize_target(target: Optional[str]) -> Optional[str]:
    if target is None:
        return None
    return "".join(target.split()).upper()


def register(registry: ToolRegistry, ucs: McpUseCases):
    async def load_manual() -> list[tuple[UUID, ManualPeriodicContribution]]:
        result = await ucs.get_contributions.execute(
            ContributionQueryRequest(real=False)
        )
        return [
            (c.id, _to_manual(UUID(entity_id), c))
            for entity_id, group in result.contributions.items()
            for c in group.periodic
            if c.source == DataSource.MANUAL
        ]

    def find_index(
        contributions: list[tuple[UUID, ManualPeriodicContribution]],
        contribution_id: UUID,
    ) -> int:
        for i, (cid, _) in enumerate(contributions):
            if cid == contribution_id:
                return i
        raise ToolError(
            "Manual contribution not found. Only manual contributions can be changed."
        )

    @registry.write("Save periodic contribution")
    async def save_contribution(
        contribution_id: Annotated[
            Optional[UUID],
            Field(
                description="Existing manual contribution ID to update. Omit to create a new one."
            ),
        ] = None,
        entity_id: Annotated[
            Optional[UUID],
            Field(
                description="Entity where the contribution is made (see list_entities)."
            ),
        ] = None,
        name: Annotated[Optional[str], Field(min_length=1)] = None,
        target_type: Optional[ContributionTargetType] = None,
        target: Annotated[
            Optional[str],
            Field(
                description="ISIN for STOCK_ETF and FUND, portfolio account number for FUND_PORTFOLIO, symbol for CRYPTO.",
                min_length=1,
            ),
        ] = None,
        target_name: Annotated[
            Optional[str],
            Field(description="Name of the target asset. Defaults to name."),
        ] = None,
        target_subtype: Annotated[
            Optional[ContributionTargetSubtype],
            Field(
                description="STOCK or ETF for STOCK_ETF; MUTUAL_FUND, PENSION_FUND or PRIVATE_EQUITY for FUND. Ignored for FUND_PORTFOLIO and CRYPTO."
            ),
        ] = None,
        amount: Annotated[
            Optional[Decimal], Field(description="Positive amount.", gt=0)
        ] = None,
        currency: Annotated[
            Optional[str],
            Field(description="ISO 4217 currency code.", min_length=3, max_length=3),
        ] = None,
        frequency: Optional[ContributionFrequency] = None,
        since: Annotated[
            Optional[date], Field(description="First contribution date.")
        ] = None,
        until: Annotated[
            Optional[date], Field(description="Last possible contribution date.")
        ] = None,
    ):
        """Create a manual periodic automatic contribution (recurring investment order), or update one by contribution_id. On update only the provided fields change. On create entity_id, name, target_type, target, amount, currency, frequency and since are required. Manual contribution IDs change after every save."""
        contributions = await load_manual()
        changes = {
            "entity_id": entity_id,
            "name": name,
            "target_type": target_type,
            "target": _normalize_target(target),
            "target_name": target_name,
            "target_subtype": target_subtype,
            "amount": Dezimal(amount) if amount is not None else None,
            "currency": currency.upper() if currency else None,
            "frequency": frequency,
            "since": since,
            "until": until,
        }

        if contribution_id:
            index = find_index(contributions, contribution_id)
            current = contributions[index][1]
            contribution = replace(
                current, **{k: v for k, v in changes.items() if v is not None}
            )
            result = "updated"
        else:
            missing = [
                field
                for field in (
                    "entity_id",
                    "name",
                    "target_type",
                    "target",
                    "amount",
                    "currency",
                    "frequency",
                    "since",
                )
                if changes[field] is None
            ]
            if missing:
                raise ToolError(f"Missing required fields: {', '.join(missing)}")
            contribution = ManualPeriodicContribution(
                **{**changes, "target_name": target_name or name}
            )
            index = None
            result = "created"

        if contribution.target_type in _NO_SUBTYPE:
            contribution = replace(contribution, target_subtype=None)

        updated = [c for _, c in contributions]
        if index is None:
            updated.append(contribution)
        else:
            updated[index] = contribution
        await ucs.update_contributions.execute(updated)
        return {result: contribution.name}

    @registry.write("Delete periodic contribution", destructive=True, idempotent=True)
    async def delete_contribution(contribution_id: ContributionId):
        """Delete a manual periodic automatic contribution. Manual contribution IDs change after every save."""
        contributions = await load_manual()
        index = find_index(contributions, contribution_id)
        await ucs.update_contributions.execute(
            [c for i, (_, c) in enumerate(contributions) if i != index]
        )
        return {"deleted": str(contribution_id)}
