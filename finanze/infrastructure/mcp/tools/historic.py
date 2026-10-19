from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID

from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.global_position import ProductType
from domain.historic import (
    DeleteManualHistoricEntryRequest,
    HistoricTxDeletion,
    PartialAmortizeManualInvestmentRequest,
    SettleManualInvestmentRequest,
    UnsettleManualInvestmentRequest,
)
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

EntityId = Annotated[UUID, Field(description="Manual entity ID (see list_entities).")]
EntryId = Annotated[
    UUID,
    Field(description="Position entry ID, from get_positions with real=false."),
]
HistoricEntryId = Annotated[
    UUID, Field(description="Historic entry ID, from get_historic_positions.")
]
ManualInvestmentType = Literal["FACTORING", "REAL_ESTATE_CF"]
NonNegative = Annotated[Decimal, Field(ge=0)]
CreateInvestmentTx = Annotated[
    bool,
    Field(
        description="Also register the initial investment transaction if it does not exist yet."
    ),
]


def _datetime(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=tzlocal())


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.write("Settle manual investment")
    async def settle_manual_investment(
        entity_id: EntityId,
        entry_id: EntryId,
        product_type: ManualInvestmentType,
        maturity: Annotated[
            Optional[date], Field(description="Settlement date. Defaults to today.")
        ] = None,
        interests: Annotated[
            Optional[Decimal],
            Field(
                description="Gross interests received. Defaults to the expected ones from the entry profitability.",
                ge=0,
            ),
        ] = None,
        fees: NonNegative = Decimal(0),
        retentions: NonNegative = Decimal(0),
        pending_capital: Annotated[
            Decimal,
            Field(
                description="Capital not returned. Above zero marks the investment as DEFAULTED instead of COMPLETED.",
                ge=0,
            ),
        ] = Decimal(0),
        create_investment_tx: CreateInvestmentTx = False,
    ):
        """Settle a manual Factoring or Real Estate Crowdfunding investment: removes it from the current position and moves it to the historic, registering its repayment and interest transactions."""
        await ucs.settle_manual_investment.execute(
            SettleManualInvestmentRequest(
                entity_id=entity_id,
                entry_id=entry_id,
                product_type=ProductType(product_type),
                maturity=_datetime(maturity),
                interests=Dezimal(interests) if interests is not None else None,
                fees=Dezimal(fees),
                retentions=Dezimal(retentions),
                pending_capital=Dezimal(pending_capital),
                create_investment_tx=create_investment_tx,
            )
        )
        return {"settled": str(entry_id)}

    @registry.write("Amortize manual investment")
    async def amortize_manual_investment(
        entity_id: EntityId,
        entry_id: EntryId,
        product_type: ManualInvestmentType,
        amount: Annotated[Decimal, Field(description="Capital returned.", ge=0)],
        payment_date: Annotated[
            Optional[date], Field(description="Payment date. Defaults to today.")
        ] = None,
        interests: Annotated[
            Decimal, Field(description="Gross interests received.", ge=0)
        ] = Decimal(0),
        fees: NonNegative = Decimal(0),
        retentions: NonNegative = Decimal(0),
        create_investment_tx: CreateInvestmentTx = False,
    ):
        """Register a partial repayment of a manual Factoring or Real Estate Crowdfunding investment that stays ongoing, reducing its pending amount and adding repayment and interest transactions."""
        await ucs.partial_amortize_manual_investment.execute(
            PartialAmortizeManualInvestmentRequest(
                entity_id=entity_id,
                entry_id=entry_id,
                product_type=ProductType(product_type),
                amount=Dezimal(amount),
                date=_datetime(payment_date),
                interests=Dezimal(interests),
                fees=Dezimal(fees),
                retentions=Dezimal(retentions),
                create_investment_tx=create_investment_tx,
            )
        )
        return {"amortized": str(entry_id)}

    @registry.write("Unsettle manual investment")
    async def unsettle_manual_investment(historic_entry_id: HistoricEntryId):
        """Revert the settlement of a manual Factoring or Real Estate Crowdfunding investment: deletes its settlement transactions and moves it back to the current position."""
        await ucs.unsettle_manual_investment.execute(
            UnsettleManualInvestmentRequest(entry_id=historic_entry_id)
        )
        return {"unsettled": str(historic_entry_id)}

    @registry.write("Delete manual historic entry", destructive=True, idempotent=True)
    async def delete_manual_historic_entry(
        historic_entry_id: HistoricEntryId,
        tx_deletion: Annotated[
            HistoricTxDeletion,
            Field(
                description="Related transactions to delete too: NONE, SETTLEMENT (only the settlement ones) or ALL."
            ),
        ] = HistoricTxDeletion.NONE,
    ):
        """Delete a manual historic Factoring or Real Estate Crowdfunding entry, optionally with its related transactions."""
        await ucs.delete_manual_historic_entry.execute(
            DeleteManualHistoricEntryRequest(
                entry_id=historic_entry_id, tx_deletion=tx_deletion
            )
        )
        return {"deleted": str(historic_entry_id)}
