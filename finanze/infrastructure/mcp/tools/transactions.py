from datetime import datetime, time
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID, uuid4

from domain.global_position import EquityType, FundType
from domain.labeling import UpdateTransactionLabelsRequest
from domain.transactions import TransactionQueryRequest, TxType
from infrastructure.controller.mappers.transaction_mapper import (
    map_add_manual_transaction,
    map_update_manual_transaction,
)
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.serialization import to_jsonable
from infrastructure.mcp.tools.common import (
    EntityIds,
    FromDate,
    Page,
    ProductTypes,
    ToDate,
)
from infrastructure.mcp.use_cases import McpUseCases

ManualProductType = Literal[
    "ACCOUNT",
    "STOCK_ETF",
    "FUND",
    "FUND_PORTFOLIO",
    "CRYPTO",
    "DEPOSIT",
    "FACTORING",
    "REAL_ESTATE_CF",
]


class ManualTransactionInput(BaseModel):
    entity_id: UUID = Field(description="Entity ID (see list_entities).")
    product_type: ManualProductType
    type: TxType = Field(
        description="ACCOUNT: INFLOW, OUTFLOW, INTEREST, FEE, TRANSFER_IN, TRANSFER_OUT. Investments: BUY, SELL, DIVIDEND, INTEREST, FEE, INVESTMENT, REPAYMENT, SPLIT, TRANSFER_IN, TRANSFER_OUT."
    )
    date: str = Field(description="ISO 8601 date or datetime.")
    name: str = Field(min_length=1)
    amount: Decimal = Field(description="Gross amount, positive.")
    currency: str = Field(min_length=3, max_length=3)
    ref: Optional[str] = Field(
        default=None,
        description="Transaction reference. Generated when creating if omitted, required when updating.",
    )
    fees: Optional[Decimal] = Field(
        default=None,
        description="Required for STOCK_ETF, FUND, FUND_PORTFOLIO, DEPOSIT, FACTORING and REAL_ESTATE_CF.",
    )
    retentions: Optional[Decimal] = Field(
        default=None,
        description="Tax withholdings. Required for DEPOSIT, FACTORING and REAL_ESTATE_CF.",
    )
    interest_rate: Optional[Decimal] = Field(default=None, description="ACCOUNT only.")
    avg_balance: Optional[Decimal] = Field(default=None, description="ACCOUNT only.")
    counterparty: Optional[str] = Field(default=None, description="ACCOUNT only.")
    iban: Optional[str] = Field(
        default=None, description="ACCOUNT and FUND_PORTFOLIO only."
    )
    label_ids: Optional[list[UUID]] = Field(
        default=None, description="ACCOUNT only. Label IDs (see list_labels)."
    )
    isin: Optional[str] = Field(
        default=None, description="STOCK_ETF (isin or ticker) and FUND (required)."
    )
    ticker: Optional[str] = Field(default=None, description="STOCK_ETF only.")
    market: Optional[str] = Field(default=None, description="STOCK_ETF and FUND.")
    shares: Optional[Decimal] = Field(
        default=None, description="Required for STOCK_ETF and FUND."
    )
    price: Optional[Decimal] = Field(
        default=None,
        description="Unit price. Required for STOCK_ETF, FUND and CRYPTO.",
    )
    order_date: Optional[str] = Field(
        default=None, description="ISO 8601. STOCK_ETF, FUND and CRYPTO."
    )
    equity_type: Optional[EquityType] = Field(
        default=None, description="STOCK_ETF only."
    )
    fund_type: Optional[FundType] = Field(default=None, description="FUND only.")
    split_ratio: Optional[Decimal] = Field(
        default=None, description="Required for SPLIT (new shares per old share)."
    )
    portfolio_name: Optional[str] = Field(
        default=None, description="FUND_PORTFOLIO only."
    )
    symbol: Optional[str] = Field(default=None, description="Required for CRYPTO.")
    currency_amount: Optional[Decimal] = Field(
        default=None, description="CRYPTO only. Amount of crypto units. Required."
    )
    contract_address: Optional[str] = Field(
        default=None, description="CRYPTO token contract address."
    )


def _to_body(tx: ManualTransactionInput) -> dict:
    body = tx.model_dump(mode="json", exclude_none=True)
    label_ids = body.pop("label_ids", None)
    if label_ids is not None:
        body["labels"] = label_ids
    return body


def _compact_tx(tx) -> dict:
    data = to_jsonable(tx)
    entity = data.pop("entity", None)
    if entity:
        data["entity_id"] = entity.get("id")
        data["entity_name"] = entity.get("name")
    return data


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("Search transactions")
    async def search_transactions(
        entities: EntityIds = None,
        product_types: ProductTypes = None,
        types: Annotated[
            Optional[list[TxType]], Field(description="Filter by transaction types.")
        ] = None,
        from_date: FromDate = None,
        to_date: ToDate = None,
        labels: Annotated[
            Optional[list[UUID]],
            Field(description="Only transactions with any of these label IDs."),
        ] = None,
        excluded_labels: Annotated[
            Optional[list[UUID]],
            Field(description="Exclude transactions with any of these label IDs."),
        ] = None,
        unlabeled: Annotated[
            bool, Field(description="Only transactions without labels.")
        ] = False,
        search: Annotated[
            Optional[str],
            Field(
                description="Free text search over name, counterparty and references.",
                max_length=100,
            ),
        ] = None,
        page: Page = 1,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ):
        """Search transactions and account movements across all entities, newest first. Account movements include counterparty, IBAN and labels; investment transactions include shares, price, fees and taxes."""
        result = await ucs.get_transactions.execute(
            TransactionQueryRequest(
                page=page,
                limit=limit,
                entities=entities,
                product_types=product_types,
                from_date=datetime.combine(from_date, time.min) if from_date else None,
                to_date=datetime.combine(to_date, time.max) if to_date else None,
                types=types,
                labels=labels,
                excluded_labels=excluded_labels,
                unlabeled=unlabeled,
                search=(search or "").strip() or None,
            )
        )
        return {
            "page": page,
            "limit": limit,
            "transactions": [_compact_tx(tx) for tx in result.transactions],
        }

    @registry.write("Add transactions")
    async def add_transactions(
        transactions: Annotated[
            list[ManualTransactionInput], Field(min_length=1, max_length=100)
        ],
    ):
        """Add one or more manual account or investment transactions. Required fields depend on product_type; see each field description."""
        bodies = [_to_body(tx) for tx in transactions]
        for body in bodies:
            body.setdefault("ref", str(uuid4()))
        await ucs.add_manual_transaction.execute(map_add_manual_transaction(bodies))
        return {"created": len(bodies)}

    @registry.write("Update manual transaction", idempotent=True)
    async def update_manual_transaction(
        tx_id: Annotated[UUID, Field(description="Transaction ID.")],
        transaction: Annotated[
            ManualTransactionInput,
            Field(description="Complete transaction data, replaces the existing one."),
        ],
    ):
        """Replace a manual transaction. Only source MANUAL transactions can be updated with this tool; transactions fetched from connected entities (REAL) or imported from Google Sheets (SHEETS) cannot be updated here."""
        if not transaction.ref:
            raise ToolError("ref is required, use the one from search_transactions.")
        await ucs.update_manual_transaction.execute(
            map_update_manual_transaction(_to_body(transaction), tx_id)
        )
        return {"updated": str(tx_id)}

    @registry.write("Delete manual transaction", destructive=True, idempotent=True)
    async def delete_manual_transaction(
        tx_id: Annotated[UUID, Field(description="Transaction ID.")],
    ):
        """Delete a manual transaction. Only source MANUAL transactions can be deleted with this tool; transactions fetched from connected entities (REAL) or imported from Google Sheets (SHEETS) cannot be deleted here."""
        await ucs.delete_manual_transaction.execute(tx_id)
        return {"deleted": str(tx_id)}

    @registry.write("Set transaction labels", idempotent=True)
    async def set_transaction_labels(
        tx_id: Annotated[UUID, Field(description="Account transaction ID.")],
        label_ids: Annotated[
            list[UUID],
            Field(description="Label IDs to set (see list_labels). Empty clears them."),
        ],
    ):
        """Set the labels of an account transaction, replacing the current ones. The labels get locked so automatic rules won't override them."""
        await ucs.update_transaction_labels.execute(
            UpdateTransactionLabelsRequest(tx_id=tx_id, label_ids=label_ids)
        )
        return {"updated": str(tx_id), "label_ids": label_ids}
