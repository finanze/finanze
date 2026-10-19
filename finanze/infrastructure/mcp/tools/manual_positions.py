from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, ClassVar, Literal, Optional, Union
from uuid import UUID

from dateutil.tz import tzlocal
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.external_integration import ExternalIntegrationId
from domain.fetch_record import DataSource
from domain.global_position import (
    AccountType,
    AssetType,
    CardType,
    EquityType,
    FundType,
    InstallmentFrequency,
    InterestType,
    LoanType,
    PositionQueryRequest,
    ProductPositions,
    ProductType,
    UpdatePositionRequest,
)
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from infrastructure.controller.mappers.manual_position_mapper import (
    map_manual_products,
)
from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

Amount = Annotated[Optional[Decimal], Field(default=None, ge=0)]
Rate = Annotated[
    Optional[Decimal],
    Field(default=None, description="Annual rate as a fraction (0.05 = 5%)."),
]
Currency = Annotated[
    Optional[str],
    Field(
        default=None, min_length=3, max_length=3, description="ISO 4217 currency code."
    ),
]
TrackerKey = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Key to update the market price automatically, usually the ISIN or ticker.",
    ),
]


class AccountInput(BaseModel):
    """Bank account. Required on create: type, total, currency."""

    required_on_create: ClassVar[tuple[str, ...]] = ("type", "total", "currency")
    product_type: Literal["ACCOUNT"]
    name: Optional[str] = None
    type: Optional[AccountType] = None
    total: Optional[Decimal] = Field(default=None, description="Balance.")
    currency: Currency
    iban: Optional[str] = None
    interest: Rate
    retained: Amount
    pending_transfers: Amount


class CardInput(BaseModel):
    """Credit or debit card. Required on create: type, currency, used."""

    required_on_create: ClassVar[tuple[str, ...]] = ("type", "currency", "used")
    product_type: Literal["CARD"]
    name: Optional[str] = None
    type: Optional[CardType] = None
    currency: Currency
    used: Amount
    limit: Amount
    active: Optional[bool] = None
    ending: Optional[str] = Field(default=None, description="Last card digits.")
    related_account: Optional[UUID] = Field(
        default=None, description="Account entry ID charged by the card."
    )


class FundPortfolioInput(BaseModel):
    """Fund portfolio grouping funds. Required on create: name, currency."""

    required_on_create: ClassVar[tuple[str, ...]] = ("name", "currency")
    product_type: Literal["FUND_PORTFOLIO"]
    name: Optional[str] = None
    currency: Currency
    initial_investment: Amount
    market_value: Amount
    account_id: Optional[UUID] = Field(
        default=None, description="Linked account entry ID of type FUND_PORTFOLIO."
    )


class FundInput(BaseModel):
    """Investment fund. Required on create: name, isin, type, shares, currency and initial_investment or average_buy_price."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "name",
        "isin",
        "type",
        "shares",
        "currency",
    )
    product_type: Literal["FUND"]
    name: Optional[str] = None
    isin: Optional[str] = None
    type: Optional[FundType] = None
    asset_type: Optional[AssetType] = None
    shares: Amount
    currency: Currency
    initial_investment: Amount
    average_buy_price: Amount
    market_value: Amount
    market: Optional[str] = None
    portfolio_id: Optional[UUID] = Field(
        default=None, description="Fund portfolio entry ID to link."
    )
    tracker_key: TrackerKey


class StockInput(BaseModel):
    """Stock or ETF. Required on create: name, ticker, isin, type, shares, currency and initial_investment or average_buy_price."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "name",
        "ticker",
        "isin",
        "type",
        "shares",
        "currency",
    )
    product_type: Literal["STOCK_ETF"]
    name: Optional[str] = None
    ticker: Optional[str] = None
    isin: Optional[str] = None
    type: Optional[EquityType] = None
    subtype: Optional[str] = None
    shares: Amount
    currency: Currency
    initial_investment: Amount
    average_buy_price: Amount
    market_value: Amount
    market: Optional[str] = None
    tracker_key: TrackerKey


class DepositInput(BaseModel):
    """Term deposit. Required on create: all fields."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "name",
        "amount",
        "currency",
        "interest_rate",
        "creation",
        "maturity",
    )
    product_type: Literal["DEPOSIT"]
    name: Optional[str] = None
    amount: Amount
    currency: Currency
    interest_rate: Rate
    creation: Optional[date] = None
    maturity: Optional[date] = None


class FactoringInput(BaseModel):
    """Factoring investment. Required on create: all fields except late_interest_rate."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "name",
        "amount",
        "currency",
        "interest_rate",
        "start",
        "maturity",
        "type",
        "state",
    )
    product_type: Literal["FACTORING"]
    name: Optional[str] = None
    amount: Amount
    currency: Currency
    interest_rate: Rate
    late_interest_rate: Rate
    start: Optional[date] = None
    maturity: Optional[date] = None
    type: Optional[str] = Field(
        default=None, description="e.g. PUBLIC_ADMIN, INSURED, NON_INSURED."
    )
    state: Optional[str] = Field(
        default=None, description="e.g. FUNDED, IN_PROGRESS, MANAGING_COLLECTION."
    )


class RealEstateCFInput(BaseModel):
    """Real estate crowdfunding investment. Required on create: name, amount, pending_amount, currency, interest_rate, start, maturity, type and state."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "name",
        "amount",
        "pending_amount",
        "currency",
        "interest_rate",
        "start",
        "maturity",
        "type",
        "state",
    )
    product_type: Literal["REAL_ESTATE_CF"]
    name: Optional[str] = None
    amount: Amount
    pending_amount: Amount
    currency: Currency
    interest_rate: Rate
    start: Optional[date] = None
    maturity: Optional[date] = None
    type: Optional[str] = Field(default=None, description="e.g. LENDING, EQUITY.")
    business_type: Optional[str] = None
    state: Optional[str] = Field(default=None, description="e.g. FUNDED, IN_PROGRESS.")
    extended_maturity: Optional[date] = None
    extended_interest_rate: Rate


class LoanInput(BaseModel):
    """Loan or mortgage. Required on create: type, currency, loan_amount, principal_outstanding, current_installment, interest_rate, creation and maturity."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "type",
        "currency",
        "loan_amount",
        "principal_outstanding",
        "current_installment",
        "interest_rate",
        "creation",
        "maturity",
    )
    product_type: Literal["LOAN"]
    name: Optional[str] = None
    type: Optional[LoanType] = None
    currency: Currency
    loan_amount: Amount
    principal_outstanding: Amount
    current_installment: Amount
    installment_interests: Amount
    installment_frequency: Optional[InstallmentFrequency] = None
    interest_rate: Rate
    interest_type: Optional[InterestType] = None
    fixed_interest_rate: Rate
    euribor_rate: Rate
    fixed_years: Optional[int] = Field(default=None, ge=0)
    creation: Optional[date] = None
    maturity: Optional[date] = None
    unpaid: Amount
    track: Optional[bool] = Field(
        default=None,
        description="Update the outstanding principal automatically as installments are paid.",
    )


class CreditInput(BaseModel):
    """Credit line. Required on create: currency, credit_limit, drawn_amount, interest_rate."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "currency",
        "credit_limit",
        "drawn_amount",
        "interest_rate",
    )
    product_type: Literal["CREDIT"]
    name: Optional[str] = None
    currency: Currency
    credit_limit: Amount
    drawn_amount: Amount
    pledged_amount: Amount
    interest_rate: Rate
    creation: Optional[date] = None


class CryptoInput(BaseModel):
    """Crypto asset holding. Required on create: symbol, name, type, amount, provider and provider_id (see search_crypto_assets). initial_investment or average_buy_price require investment_currency."""

    required_on_create: ClassVar[tuple[str, ...]] = (
        "symbol",
        "name",
        "type",
        "amount",
        "provider",
        "provider_id",
    )
    product_type: Literal["CRYPTO"]
    symbol: Optional[str] = None
    name: Optional[str] = None
    type: Optional[CryptoCurrencyType] = None
    amount: Amount
    contract_address: Optional[str] = None
    provider: Optional[ExternalIntegrationId] = None
    provider_id: Optional[str] = Field(
        default=None, description="Asset ID in the provider."
    )
    market_value: Amount
    currency: Currency
    initial_investment: Amount
    average_buy_price: Amount
    investment_currency: Currency


PositionInput = Annotated[
    Union[
        AccountInput,
        CardInput,
        FundPortfolioInput,
        FundInput,
        StockInput,
        DepositInput,
        FactoringInput,
        RealEstateCFInput,
        LoanInput,
        CreditInput,
        CryptoInput,
    ],
    Field(
        discriminator="product_type",
        description="Entry fields, product_type selects the kind of entry.",
    ),
]
ManualProductType = Literal[
    "ACCOUNT",
    "CARD",
    "FUND_PORTFOLIO",
    "FUND",
    "STOCK_ETF",
    "DEPOSIT",
    "FACTORING",
    "REAL_ESTATE_CF",
    "LOAN",
    "CREDIT",
    "CRYPTO",
]
EntryId = Annotated[
    UUID, Field(description="Position entry ID, from get_positions with real=false.")
]

_DATETIME_FIELDS = {
    ProductType.DEPOSIT: "creation",
    ProductType.FACTORING: "start",
    ProductType.REAL_ESTATE_CF: "start",
}
_UPPERCASE_FIELDS = ("currency", "investment_currency", "symbol", "ticker", "isin")
_INVESTMENT_TYPES = {ProductType.FACTORING, ProductType.REAL_ESTATE_CF}
_QUANTITY_FIELDS = {
    ProductType.FUND: "shares",
    ProductType.STOCK_ETF: "shares",
    ProductType.CRYPTO: "amount",
}
_LINKED_TYPES = {
    ProductType.ACCOUNT: (ProductType.CARD, ProductType.FUND_PORTFOLIO),
    ProductType.FUND_PORTFOLIO: (ProductType.FUND,),
}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Dezimal, UUID)):
        return str(value)
    return value


def _payload(entry) -> dict:
    data = _plain(entry)
    if "manual_data" in data and data["manual_data"] is None:
        data["manual_data"] = {}
    return data


def _entries(products: ProductPositions, product_type: ProductType) -> list:
    container = products.get(product_type)
    if container is None:
        return []
    if product_type == ProductType.CRYPTO:
        return [asset for wallet in container.entries for asset in wallet.assets]
    return list(container.entries)


def _container(product_type: ProductType, entries: list[dict]) -> dict:
    if product_type == ProductType.CRYPTO:
        return {"entries": [{"assets": entries}]}
    return {"entries": entries}


def _local_datetime(value: str) -> str:
    d = date.fromisoformat(value)
    return datetime(d.year, d.month, d.day, tzinfo=tzlocal()).isoformat()


def _reset_cost_basis(entry: dict, changes: dict, quantity_field: str):
    has_total = "initial_investment" in changes
    has_average = "average_buy_price" in changes
    if has_total and not has_average:
        entry["average_buy_price"] = None
    elif has_average and not has_total:
        entry["initial_investment"] = None
    elif (
        not has_total
        and quantity_field in changes
        and entry.get("average_buy_price") is not None
    ):
        entry["initial_investment"] = None


def _apply(product_type: ProductType, base: dict, position: BaseModel) -> dict:
    changes = position.model_dump(
        mode="json", exclude_none=True, exclude={"product_type"}
    )
    entry = dict(base)
    for key in _UPPERCASE_FIELDS:
        if key in changes:
            changes[key] = changes[key].upper()
    datetime_field = _DATETIME_FIELDS.get(product_type)
    if datetime_field in changes:
        changes[datetime_field] = _local_datetime(changes[datetime_field])
    if "tracker_key" in changes or "track" in changes:
        manual_data = dict(entry.get("manual_data") or {})
        for key in ("tracker_key", "track"):
            if key in changes:
                manual_data[key] = changes.pop(key)
        entry["manual_data"] = manual_data
    if "portfolio_id" in changes:
        entry["portfolio"] = {"id": changes.pop("portfolio_id")}
    provider = changes.pop("provider", None)
    provider_id = changes.pop("provider_id", None)
    quantity_field = _QUANTITY_FIELDS.get(product_type)
    if base and quantity_field:
        _reset_cost_basis(entry, changes, quantity_field)
    entry.update(changes)

    if product_type in (ProductType.FUND, ProductType.STOCK_ETF):
        entry.setdefault("manual_data", {})
    if product_type == ProductType.CRYPTO:
        if (provider is None) != (provider_id is None):
            raise ToolError("provider and provider_id must be provided together.")
        asset = dict(
            entry.get("crypto_asset")
            or {"name": entry.get("name"), "symbol": entry.get("symbol")}
        )
        if provider:
            asset["external_ids"] = {provider: provider_id}
        entry["crypto_asset"] = asset
        entry.setdefault("market_value", None)
        entry.setdefault("currency", None)
    return entry


def _unlink(product_type: ProductType, entries: list[dict], target_id: str) -> bool:
    unlinked = False
    for entry in entries:
        if product_type == ProductType.CARD:
            if entry.get("related_account") == target_id:
                entry["related_account"] = None
                unlinked = True
        elif product_type == ProductType.FUND_PORTFOLIO:
            if entry.get("account_id") == target_id:
                entry["account_id"] = None
                entry["account"] = None
                unlinked = True
        elif (entry.get("portfolio") or {}).get("id") == target_id:
            entry["portfolio"] = None
            unlinked = True
    return unlinked


def register(registry: ToolRegistry, ucs: McpUseCases):
    async def load_products(
        entity_id: UUID, product_types: list[ProductType]
    ) -> ProductPositions:
        result = await ucs.get_position.execute(
            PositionQueryRequest(
                entities=[entity_id], real=False, products=product_types
            )
        )
        position = next(
            (
                p
                for p in result.positions.get(str(entity_id), [])
                if p.source == DataSource.MANUAL
            ),
            None,
        )
        return position.products if position else {}

    def find_index(entries: list[dict], entry_id: UUID) -> int:
        for i, entry in enumerate(entries):
            if entry.get("id") == str(entry_id):
                return i
        raise ToolError(
            "Manual position entry not found. Use get_positions with real=false to get the current entry IDs."
        )

    @registry.write("Save manual position")
    async def save_manual_position(
        position: PositionInput,
        entity_id: Annotated[
            Optional[UUID],
            Field(description="Entity to add the entry to (see list_entities)."),
        ] = None,
        new_entity_name: Annotated[
            Optional[str],
            Field(
                description="Create a new manual entity with this name instead of using entity_id.",
                min_length=1,
            ),
        ] = None,
        entry_id: Annotated[
            Optional[UUID],
            Field(
                description="Existing entry ID to update, from get_positions with real=false. Requires entity_id. Omit to create."
            ),
        ] = None,
        create_investment_tx: Annotated[
            bool,
            Field(
                description="When creating a FACTORING or REAL_ESTATE_CF entry, also register its investment transaction."
            ),
        ] = True,
    ):
        """Create a manually tracked position entry (account, card, fund, stock, deposit, loan, crypto...), or update one by entry_id. Provide either entity_id or new_entity_name. On update only the provided fields change. Entry IDs change after every save."""
        if (entity_id is None) == (new_entity_name is None):
            raise ToolError("Provide either entity_id or new_entity_name.")
        if entry_id and entity_id is None:
            raise ToolError("entry_id requires entity_id.")

        product_type = ProductType(position.product_type)
        entries = (
            [
                _payload(e)
                for e in _entries(
                    await load_products(entity_id, [product_type]), product_type
                )
            ]
            if entity_id
            else []
        )

        if entry_id:
            index = find_index(entries, entry_id)
            entries[index] = _apply(product_type, entries[index], position)
        else:
            missing = [
                f for f in position.required_on_create if getattr(position, f) is None
            ]
            if missing:
                raise ToolError(f"Missing required fields: {', '.join(missing)}")
            entries.append(_apply(product_type, {}, position))
            index = len(entries) - 1

        request = UpdatePositionRequest(
            products=map_manual_products(
                {product_type.value: _container(product_type, entries)}
            ),
            entity_id=entity_id,
            new_entity_name=new_entity_name,
            create_investment_txs=create_investment_tx
            and entry_id is None
            and product_type in _INVESTMENT_TYPES,
        )
        saved_entity_id = await ucs.update_position.execute(request)

        new_entry_id = _entries(request.products, product_type)[index].id
        return {
            "updated" if entry_id else "created": str(new_entry_id),
            "entity_id": str(saved_entity_id),
        }

    @registry.write("Delete manual position", destructive=True, idempotent=True)
    async def delete_manual_position(
        entity_id: Annotated[UUID, Field(description="Entity of the entry.")],
        product_type: ManualProductType,
        entry_id: EntryId,
    ):
        """Delete a manually tracked position entry. Deleting an account unlinks its cards and fund portfolios, deleting a fund portfolio unlinks its funds. Entry IDs change after every save."""
        main_type = ProductType(product_type)
        linked_types = _LINKED_TYPES.get(main_type, ())
        products = await load_products(entity_id, [main_type, *linked_types])

        entries = [_payload(e) for e in _entries(products, main_type)]
        index = find_index(entries, entry_id)
        del entries[index]
        raw = {main_type.value: _container(main_type, entries)}

        for linked_type in linked_types:
            linked = [_payload(e) for e in _entries(products, linked_type)]
            if _unlink(linked_type, linked, str(entry_id)):
                raw[linked_type.value] = _container(linked_type, linked)

        await ucs.update_position.execute(
            UpdatePositionRequest(
                products=map_manual_products(raw),
                entity_id=entity_id,
                create_investment_txs=False,
            )
        )
        return {"deleted": str(entry_id)}
