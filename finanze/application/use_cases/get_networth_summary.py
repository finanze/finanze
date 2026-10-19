from datetime import datetime
from typing import Optional

from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.position_port import PositionPort
from application.ports.real_estate_port import RealEstatePort
from dateutil.tz import tzlocal
from domain.commodity import (
    COMMODITY_SYMBOLS,
    WEIGHT_CONVERSIONS,
    CommodityRegister,
    WeightUnit,
)
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates
from domain.global_position import (
    CardType,
    CryptoCurrencyPosition,
    GlobalPosition,
    Loan,
    PositionQueryRequest,
    ProductType,
)
from domain.networth_summary import (
    REAL_ESTATE_BUCKET,
    REAL_ESTATE_RESIDENCE_BUCKET,
    NetworthSummary,
    NetworthSummaryQuery,
)
from domain.real_estate import RealEstate, RealEstateFlowSubtype
from domain.use_cases.get_networth_summary import GetNetworthSummary

_CURRENCY_ALIASES = {"BNFCR": "USD", "PUSD": "USD"}
_ZERO = Dezimal(0)


def _normalize_currency(currency: Optional[str]) -> Optional[str]:
    if not currency:
        return None
    return _CURRENCY_ALIASES.get(currency.upper(), currency)


def _rate_entry(rates: ExchangeRates, target: str, key: Optional[str]):
    normalized_target = _normalize_currency(target)
    normalized_key = _normalize_currency(key)
    if not normalized_target or not normalized_key:
        return None
    variants = (normalized_key, normalized_key.upper(), normalized_key.lower())
    for candidate in (rates.get(target), rates.get(normalized_target.upper())):
        if not candidate:
            continue
        for variant in variants:
            value = candidate.get(variant)
            if value is not None:
                return value
    return None


def _convert(
    amount: Optional[Dezimal],
    currency: Optional[str],
    target: str,
    rates: ExchangeRates,
) -> Dezimal:
    if amount is None or amount == _ZERO:
        return _ZERO
    source = _normalize_currency(currency)
    normalized_target = _normalize_currency(target)
    if source and normalized_target and source.upper() == normalized_target.upper():
        return amount
    rate = _rate_entry(rates, normalized_target or target, source or currency)
    if rate is None or rate == _ZERO:
        return _ZERO
    return amount / rate


def _crypto_rate_key(asset: CryptoCurrencyPosition) -> Optional[str]:
    if asset.type == CryptoCurrencyType.TOKEN and asset.contract_address:
        return asset.contract_address.lower()
    return asset.symbol.upper() if asset.symbol else None


def _crypto_asset_value(
    asset: CryptoCurrencyPosition, target: str, rates: ExchangeRates
) -> Dezimal:
    amount = asset.amount or _ZERO
    rate_key = _crypto_rate_key(asset)
    prefer_market_value = asset.crypto_asset is None and asset.market_value is not None

    if not prefer_market_value and amount > 0 and rate_key:
        rate = _rate_entry(rates, target, rate_key)
        if rate is not None and rate != _ZERO:
            value = amount / rate
            if value > 0:
                return value

    if asset.market_value is None:
        return _ZERO
    source = asset.currency or target
    if source == target:
        return asset.market_value
    if _rate_entry(rates, target, source) is None:
        return _ZERO
    return _convert(asset.market_value, source, target, rates)


def _commodity_value(
    commodity: CommodityRegister, target: str, rates: ExchangeRates
) -> Dezimal:
    amount = commodity.amount
    if amount is None or amount <= 0:
        return _ZERO
    amount_in_troy_ounces = amount
    if commodity.unit == WeightUnit.GRAM:
        amount_in_troy_ounces = (
            amount * WEIGHT_CONVERSIONS[WeightUnit.GRAM][WeightUnit.TROY_OUNCE]
        )
    price = (rates.get(target) or {}).get(COMMODITY_SYMBOLS.get(commodity.type))
    if price is None or price == _ZERO:
        return amount
    return amount_in_troy_ounces / price


def _real_estate_equity(
    real_estate: RealEstate,
    linked_loans: dict[str, Loan],
    target: str,
    rates: ExchangeRates,
) -> Dezimal:
    market = real_estate.valuation_info.estimated_market_value or _ZERO
    outstanding = _ZERO
    for flow in real_estate.flows:
        if flow.flow_subtype != RealEstateFlowSubtype.LOAN:
            continue
        loan = (
            linked_loans.get(flow.linked_loan_hash) if flow.linked_loan_hash else None
        )
        principal = (
            loan.principal_outstanding
            if loan
            else getattr(flow.payload, "principal_outstanding", None)
        )
        outstanding = outstanding + (principal or _ZERO)
    owned = max(market - outstanding, _ZERO)
    return _convert(owned, real_estate.currency, target, rates)


def _entries(position: GlobalPosition, product_type: ProductType) -> list:
    return getattr(position.products.get(product_type), "entries", None) or []


_VALUED_PRODUCTS = (
    (ProductType.FUND, "market_value"),
    (ProductType.STOCK_ETF, "market_value"),
    (ProductType.DEPOSIT, "amount"),
    (ProductType.REAL_ESTATE_CF, "pending_amount"),
    (ProductType.FACTORING, "amount"),
)


def _asset_distribution(
    positions: list[GlobalPosition], target: str, rates: ExchangeRates
) -> dict[str, Dezimal]:
    distribution: dict[str, Dezimal] = {}

    def add(bucket: str, value: Dezimal):
        distribution[bucket] = distribution.get(bucket, _ZERO) + value

    for position in positions:
        accounts = _entries(position, ProductType.ACCOUNT)
        if accounts:
            accounts_total = sum(
                (_convert(a.total, a.currency, target, rates) for a in accounts),
                _ZERO,
            )
            if accounts_total != _ZERO:
                add(ProductType.ACCOUNT.value, accounts_total)

        for product_type, field in _VALUED_PRODUCTS:
            items = _entries(position, product_type)
            if items:
                add(
                    product_type.value,
                    sum(
                        (
                            _convert(getattr(i, field), i.currency, target, rates)
                            for i in items
                        ),
                        _ZERO,
                    ),
                )

        crowdlending = position.products.get(ProductType.CROWDLENDING)
        crowdlending_total = getattr(crowdlending, "total", None)
        if crowdlending_total is not None and crowdlending_total != _ZERO:
            add(
                ProductType.CROWDLENDING.value,
                _convert(crowdlending_total, crowdlending.currency, target, rates),
            )

        wallets = _entries(position, ProductType.CRYPTO)
        if wallets:
            add(
                ProductType.CRYPTO.value,
                sum(
                    (
                        _crypto_asset_value(asset, target, rates)
                        for wallet in wallets
                        for asset in wallet.assets
                        if asset.crypto_asset is not None
                        or asset.market_value is not None
                    ),
                    _ZERO,
                ),
            )

        commodities = _entries(position, ProductType.COMMODITY)
        if commodities:
            add(
                ProductType.COMMODITY.value,
                sum((_commodity_value(c, target, rates) for c in commodities), _ZERO),
            )

        for derivative in _entries(position, ProductType.DERIVATIVE):
            bucket = (
                derivative.underlying_asset.value
                if derivative.underlying_asset
                else ProductType.CRYPTO.value
            )
            add(
                bucket,
                _convert(derivative.market_value, derivative.currency, target, rates),
            )

        forecasts = _entries(position, ProductType.MARKET_FORECAST)
        if forecasts:
            add(
                ProductType.MARKET_FORECAST.value,
                sum(
                    (
                        _convert(f.market_value, f.currency, target, rates)
                        for f in forecasts
                    ),
                    _ZERO,
                ),
            )

    return distribution


class GetNetworthSummaryImpl(GetNetworthSummary):
    def __init__(
        self,
        position_port: PositionPort,
        entity_port: EntityPort,
        real_estate_port: RealEstatePort,
        exchange_rate_storage: ExchangeRateStorage,
    ):
        self._position_port = position_port
        self._entity_port = entity_port
        self._real_estate_port = real_estate_port
        self._exchange_rate_storage = exchange_rate_storage

    async def execute(self, query: NetworthSummaryQuery) -> NetworthSummary:
        target = query.base_currency
        excluded_entities = [
            e.id for e in await self._entity_port.get_disabled_entities()
        ]
        positions_by_entity = await self._position_port.get_last_by_entity_broken_down(
            PositionQueryRequest(excluded_entities=excluded_entities)
        )
        real_estate = await self._real_estate_port.get_all()
        linked_loans = await self._get_linked_loans(real_estate)
        rates = await self._exchange_rate_storage.get() or {}

        positions = [
            position
            for entity_positions in positions_by_entity.values()
            for position in entity_positions or []
        ]

        breakdown = _asset_distribution(positions, target, rates)

        investment_equity = sum(
            (
                _real_estate_equity(estate, linked_loans, target, rates)
                for estate in real_estate
                if not estate.basic_info.is_residence
            ),
            _ZERO,
        )
        residence_equity = sum(
            (
                _real_estate_equity(estate, linked_loans, target, rates)
                for estate in real_estate
                if estate.basic_info.is_residence
            ),
            _ZERO,
        )
        if investment_equity != _ZERO:
            breakdown[REAL_ESTATE_BUCKET] = investment_equity
        if residence_equity != _ZERO:
            breakdown[REAL_ESTATE_RESIDENCE_BUCKET] = residence_equity

        linked_loan_hashes = {
            flow.linked_loan_hash
            for estate in real_estate
            for flow in estate.flows
            if flow.linked_loan_hash
        }
        card_used = sum(
            (
                _convert(card.used, card.currency, target, rates)
                for position in positions
                for card in _entries(position, ProductType.CARD)
                if card.type == CardType.CREDIT
            ),
            _ZERO,
        )
        credit_drawn = sum(
            (
                _convert(credit.drawn_amount, credit.currency, target, rates)
                for position in positions
                for credit in _entries(position, ProductType.CREDIT)
            ),
            _ZERO,
        )
        unlinked_loans = sum(
            (
                _convert(loan.principal_outstanding, loan.currency, target, rates)
                for position in positions
                for loan in _entries(position, ProductType.LOAN)
                if not (loan.hash and loan.hash in linked_loan_hashes)
            ),
            _ZERO,
        )
        if card_used != _ZERO:
            breakdown[ProductType.CARD.value] = -card_used
        if credit_drawn != _ZERO:
            breakdown[ProductType.CREDIT.value] = -credit_drawn
        if unlinked_loans != _ZERO:
            breakdown[ProductType.LOAN.value] = -unlinked_loans

        total = sum(breakdown.values(), _ZERO)

        return NetworthSummary(
            currency=target,
            date=datetime.now(tzlocal()).date(),
            total=total,
            breakdown=breakdown,
        )

    async def _get_linked_loans(self, real_estate: list[RealEstate]) -> dict[str, Loan]:
        hashes = {
            flow.linked_loan_hash
            for estate in real_estate
            for flow in estate.flows
            if flow.flow_subtype == RealEstateFlowSubtype.LOAN and flow.linked_loan_hash
        }
        if not hashes:
            return {}
        return await self._position_port.get_loans_by_hash(list(hashes))
