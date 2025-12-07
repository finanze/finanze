from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict
from uuid import UUID

from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.exception.exceptions import MissingFieldsError
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    AssetType,
    Card,
    Cards,
    CardType,
    Crowdlending,
    Deposit,
    Deposits,
    EquityType,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ManualEntryData,
    ProductPositions,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
    StockDetail,
    StockInvestments,
)


def _uuid(value: Any):
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


def _dez(value: Any):
    if value is None:
        return None
    return Dezimal(str(value))


def _date(value: Any):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(value, datetime):
        return value.date()
    raise ValueError(f"Invalid date value: {value}")


def _dt(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=tzlocal())
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError(f"Invalid datetime value: {value}")


def _map_manual_data(entry: dict) -> ManualEntryData:
    return ManualEntryData(
        tracker_key=entry.get("tracker_key"),
    )


def _map_accounts(entries: list[dict]) -> Accounts:
    result = []
    for e in entries:
        for req in ("total", "currency", "type"):
            if req not in e:
                raise MissingFieldsError([req])
        result.append(
            Account(
                id=_uuid(e.get("id")),
                total=_dez(e["total"]),
                currency=e["currency"],
                type=AccountType(e["type"]),
                name=e.get("name"),
                iban=e.get("iban"),
                interest=_dez(e.get("interest")),
                retained=_dez(e.get("retained")),
                pending_transfers=_dez(e.get("pending_transfers")),
                source=DataSource.MANUAL,
            )
        )
    return Accounts(result)


def _map_cards(entries: list[dict]) -> Cards:
    result = []
    for e in entries:
        for req in ("currency", "type", "used"):
            if req not in e:
                raise MissingFieldsError([req])
        result.append(
            Card(
                id=_uuid(e.get("id")),
                currency=e["currency"],
                type=CardType(e["type"]),
                used=_dez(e["used"]),
                active=bool(e["active"]) if e.get("active") is not None else True,
                limit=_dez(e.get("limit")),
                name=e.get("name"),
                ending=e.get("ending"),
                related_account=_uuid(e.get("related_account")),
                source=DataSource.MANUAL,
            )
        )
    return Cards(result)


def _map_fund_portfolios(entries: list[dict]) -> FundPortfolios:
    result = []
    for e in entries:
        result.append(
            FundPortfolio(
                id=_uuid(e.get("id")),
                name=e.get("name"),
                currency=e.get("currency"),
                initial_investment=_dez(e.get("initial_investment")),
                market_value=_dez(e.get("market_value")),
                account_id=_uuid(e.get("account_id")),
                source=DataSource.MANUAL,
            )
        )
    return FundPortfolios(result)


def _map_funds(entries: list[dict]) -> FundInvestments:
    result = []
    for e in entries:
        for req in ("name", "isin", "shares", "currency", "manual_data"):
            if req not in e:
                raise MissingFieldsError([req])
        portfolio_data = e.get("portfolio")
        portfolio = None
        if isinstance(portfolio_data, dict):
            portfolio = FundPortfolio(
                id=_uuid(portfolio_data.get("id")),
                name=portfolio_data.get("name"),
                currency=portfolio_data.get("currency"),
                initial_investment=_dez(portfolio_data.get("initial_investment")),
                market_value=_dez(portfolio_data.get("market_value")),
                source=DataSource.MANUAL,
            )
        init_inv = _dez(e.get("initial_investment"))
        avg_buy = _dez(e.get("average_buy_price"))
        market_value = _dez(e.get("market_value")) or Dezimal(0)
        result.append(
            FundDetail(
                id=_uuid(e.get("id")),
                name=e["name"],
                isin=e["isin"],
                market=e.get("market"),
                shares=_dez(e["shares"]),
                initial_investment=init_inv,
                average_buy_price=avg_buy,
                market_value=market_value,
                currency=e["currency"],
                type=FundType(e["type"]),
                asset_type=AssetType(e.get("asset_type"))
                if e.get("asset_type")
                else None,
                portfolio=portfolio,
                manual_data=_map_manual_data(e["manual_data"]),
                source=DataSource.MANUAL,
            )
        )
    return FundInvestments(result)


def _map_real_estate_cf(entries: list[dict]) -> RealEstateCFInvestments:
    result = []
    for e in entries:
        for req in (
            "name",
            "amount",
            "pending_amount",
            "currency",
            "interest_rate",
            "start",
            "maturity",
            "type",
            "state",
        ):
            if req not in e:
                raise MissingFieldsError([req])
        result.append(
            RealEstateCFDetail(
                id=_uuid(e.get("id")),
                name=e["name"],
                amount=_dez(e["amount"]),
                pending_amount=_dez(e["pending_amount"]),
                currency=e["currency"],
                interest_rate=_dez(e["interest_rate"]),
                start=_dt(e["start"]),
                maturity=_date(e["maturity"]),
                type=e["type"],
                business_type=e.get("business_type", ""),
                state=e["state"],
                extended_maturity=_date(e.get("extended_maturity")),
                extended_interest_rate=_dez(e.get("extended_interest_rate"))
                if e.get("extended_interest_rate")
                else None,
                source=DataSource.MANUAL,
            )
        )
    return RealEstateCFInvestments(result)


def _map_factoring(entries: list[dict]) -> FactoringInvestments:
    result = []
    for e in entries:
        for req in (
            "name",
            "amount",
            "currency",
            "interest_rate",
            "maturity",
            "type",
            "state",
            "start",
        ):
            if req not in e:
                raise MissingFieldsError([req])
        result.append(
            FactoringDetail(
                id=_uuid(e.get("id")),
                name=e["name"],
                amount=_dez(e["amount"]),
                currency=e["currency"],
                interest_rate=_dez(e["interest_rate"]),
                start=_dt(e["start"]),
                maturity=_date(e["maturity"]),
                type=e["type"],
                state=e["state"],
                late_interest_rate=_dez(e.get("late_interest_rate"))
                if e.get("late_interest_rate")
                else None,
                source=DataSource.MANUAL,
            )
        )
    return FactoringInvestments(result)


def _map_deposits(entries: list[dict]) -> Deposits:
    result = []
    for e in entries:
        for req in (
            "name",
            "amount",
            "currency",
            "interest_rate",
            "creation",
            "maturity",
        ):
            if req not in e:
                raise MissingFieldsError([req])
        result.append(
            Deposit(
                id=_uuid(e.get("id")),
                name=e["name"],
                amount=_dez(e["amount"]),
                currency=e["currency"],
                expected_interests=Dezimal(0),
                interest_rate=_dez(e["interest_rate"]),
                creation=_dt(e["creation"]),
                maturity=_date(e["maturity"]),
                source=DataSource.MANUAL,
            )
        )
    return Deposits(result)


def _map_loans(entries: list[dict]) -> Loans:
    result = []
    for e in entries:
        for req in (
            "type",
            "currency",
            "current_installment",
            "interest_rate",
            "loan_amount",
            "creation",
            "maturity",
            "principal_outstanding",
        ):
            if req not in e:
                raise MissingFieldsError([req])
        result.append(
            Loan(
                id=_uuid(e.get("id")),
                type=LoanType(e["type"]),
                currency=e["currency"],
                current_installment=_dez(e["current_installment"]),
                interest_rate=_dez(e["interest_rate"]),
                loan_amount=_dez(e["loan_amount"]),
                creation=_date(e["creation"]),
                maturity=_date(e["maturity"]),
                principal_outstanding=_dez(e["principal_outstanding"]),
                principal_paid=_dez(e.get("principal_paid")),
                interest_type=InterestType(e.get("interest_type", InterestType.FIXED)),
                next_payment_date=_date(e.get("next_payment_date")),
                euribor_rate=_dez(e.get("euribor_rate")),
                fixed_years=e.get("fixed_years"),
                name=e.get("name"),
                unpaid=_dez(e.get("unpaid")),
                source=DataSource.MANUAL,
            )
        )
    return Loans(result)


def _map_stocks(entries: list[dict]) -> StockInvestments:
    result = []
    for e in entries:
        for req in (
            "name",
            "ticker",
            "isin",
            "shares",
            "currency",
            "type",
            "manual_data",
        ):
            if req not in e:
                raise MissingFieldsError([req])
        init_inv = _dez(e.get("initial_investment"))
        avg_buy = _dez(e.get("average_buy_price"))
        market_value = _dez(e.get("market_value")) or Dezimal(0)
        result.append(
            StockDetail(
                id=_uuid(e.get("id")),
                name=e["name"],
                ticker=e["ticker"],
                isin=e["isin"],
                market=e.get("market", ""),
                shares=_dez(e["shares"]),
                initial_investment=init_inv,
                average_buy_price=avg_buy,
                market_value=market_value,
                currency=e["currency"],
                type=EquityType(e["type"]),
                subtype=e.get("subtype"),
                manual_data=_map_manual_data(e["manual_data"]),
                source=DataSource.MANUAL,
            )
        )
    return StockInvestments(result)


def _map_crowdlending(entries: list[dict]) -> Crowdlending:
    if not entries:
        raise MissingFieldsError(["crowdlending entry"])
    e = entries[0]
    return Crowdlending(
        id=_uuid(e.get("id")) or UUID(int=0),
        total=_dez(e.get("total")),
        weighted_interest_rate=_dez(e.get("weighted_interest_rate")),
        currency=e.get("currency"),
        distribution=e.get("distribution"),
        entries=[],
    )


_MAPPER_DISPATCH = {
    ProductType.ACCOUNT: _map_accounts,
    ProductType.CARD: _map_cards,
    ProductType.FUND_PORTFOLIO: _map_fund_portfolios,
    ProductType.FUND: _map_funds,
    ProductType.REAL_ESTATE_CF: _map_real_estate_cf,
    ProductType.FACTORING: _map_factoring,
    ProductType.DEPOSIT: _map_deposits,
    ProductType.LOAN: _map_loans,
    ProductType.STOCK_ETF: _map_stocks,
    ProductType.CROWDLENDING: _map_crowdlending,
}


def map_manual_products(raw_products: Dict[str, Any] | None) -> ProductPositions:
    products: ProductPositions = {}
    if not raw_products:
        return products
    for key, value in raw_products.items():
        try:
            ptype = ProductType(key)
        except ValueError:
            continue
        if value is None:
            continue
        if (
            isinstance(value, dict)
            and "entries" in value
            and isinstance(value["entries"], list)
        ):
            entries_payload = value["entries"]
        elif isinstance(value, list):
            entries_payload = value
        elif isinstance(value, dict):
            entries_payload = [value]
        else:
            raise ValueError(f"Unsupported payload shape for product '{ptype.value}'")
        mapper = _MAPPER_DISPATCH.get(ptype)
        if not mapper:
            continue
        products[ptype] = mapper(entries_payload)
    return products
