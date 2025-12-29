from datetime import datetime
from typing import Optional
from uuid import UUID

from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import (
    AccountTx,
    BaseTx,
    DepositTx,
    FactoringTx,
    FundPortfolioTx,
    FundTx,
    RealEstateCFTx,
    StockTx,
    TxType,
)


def _parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzlocal())
    return dt


def _build_account(body: dict, base_kwargs: dict, tx_id: Optional[UUID]) -> BaseTx:
    return AccountTx(
        id=tx_id,
        fees=Dezimal(body.get("fees", 0)),
        retentions=Dezimal(body.get("retentions", 0)),
        interest_rate=Dezimal(body["interest_rate"])
        if body.get("interest_rate")
        else None,
        avg_balance=Dezimal(body["avg_balance"]) if body.get("avg_balance") else None,
        net_amount=None,
        **base_kwargs,
    )


def _require(body: dict, product_label: str, required: list[str]):
    missing = [f for f in required if f not in body]
    if missing:
        raise ValueError(f"Missing fields for {product_label}: {', '.join(missing)}")


def _build_stock(body: dict, base_kwargs: dict, tx_id: Optional[UUID]) -> BaseTx:
    _require(body, "STOCK_ETF", ["shares", "price", "fees"])
    order_date = _parse_datetime(body["order_date"]) if body.get("order_date") else None
    return StockTx(
        id=tx_id,
        isin=body.get("isin"),
        ticker=body.get("ticker"),
        market=body.get("market"),
        shares=Dezimal(body["shares"]),
        price=Dezimal(body["price"]),
        net_amount=None,
        fees=Dezimal(body["fees"]),
        retentions=Dezimal(body["retentions"]) if body.get("retentions") else None,
        order_date=order_date,
        linked_tx=body.get("linked_tx"),
        equity_type=body.get("equity_type"),
        **base_kwargs,
    )


def _build_fund(body: dict, base_kwargs: dict, tx_id: Optional[UUID]) -> BaseTx:
    _require(body, "FUND", ["isin", "shares", "price", "fees"])
    order_date = _parse_datetime(body["order_date"]) if body.get("order_date") else None
    return FundTx(
        id=tx_id,
        isin=body["isin"],
        market=body.get("market"),
        shares=Dezimal(body["shares"]),
        price=Dezimal(body["price"]),
        net_amount=None,
        fees=Dezimal(body["fees"]),
        retentions=Dezimal(body["retentions"]) if body.get("retentions") else None,
        order_date=order_date,
        fund_type=body.get("fund_type"),
        **base_kwargs,
    )


def _build_fund_portfolio(
    body: dict, base_kwargs: dict, tx_id: Optional[UUID]
) -> BaseTx:
    _require(body, "FUND_PORTFOLIO", ["fees"])
    return FundPortfolioTx(
        id=tx_id,
        fees=Dezimal(body["fees"]),
        portfolio_name=body.get("portfolio_name"),
        iban=body.get("iban"),
        **base_kwargs,
    )


def _build_factoring_like(
    body: dict, base_kwargs: dict, tx_id: Optional[UUID], product_type: ProductType
) -> BaseTx:
    # net_amount removed; only fees and retentions required
    _require(body, product_type.value, ["fees", "retentions"])
    cls_map = {
        ProductType.FACTORING: FactoringTx,
        ProductType.REAL_ESTATE_CF: RealEstateCFTx,
        ProductType.DEPOSIT: DepositTx,
    }
    cls = cls_map[product_type]
    return cls(
        id=tx_id,
        net_amount=None,
        fees=Dezimal(body["fees"]),
        retentions=Dezimal(body["retentions"]),
        **base_kwargs,
    )


_DISPATCH = {
    ProductType.ACCOUNT: _build_account,
    ProductType.STOCK_ETF: _build_stock,
    ProductType.FUND: _build_fund,
    ProductType.FUND_PORTFOLIO: _build_fund_portfolio,
}


def map_manual_transaction(body: dict, tx_id: Optional[UUID] = None) -> BaseTx:
    if not isinstance(body, dict):
        raise ValueError("Body must be a JSON object")

    try:
        product_type = ProductType(body["product_type"])
        entity_id = UUID(body["entity_id"])
        date_dt = _parse_datetime(body["date"])
    except KeyError as e:
        raise ValueError(f"Missing required field: {e.args[0]}") from e
    except TypeError as e:
        raise ValueError(str(e)) from e

    for field in ("ref", "name", "amount", "currency", "type"):
        if field not in body:
            raise ValueError(f"Missing required field: {field}")

    tx_type = TxType(body["type"])

    try:
        amount = Dezimal(body["amount"])
    except Exception as e:
        raise ValueError(f"Invalid amount: {e}") from e

    entity_stub = Entity(
        id=entity_id,
        name="",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )

    base_kwargs = {
        "ref": body["ref"],
        "name": body["name"],
        "amount": amount,
        "currency": body["currency"],
        "type": tx_type,
        "date": date_dt,
        "entity": entity_stub,
        "source": DataSource.MANUAL,
        "product_type": product_type,
    }

    if product_type in (
        ProductType.FACTORING,
        ProductType.REAL_ESTATE_CF,
        ProductType.DEPOSIT,
    ):
        return _build_factoring_like(body, base_kwargs, tx_id, product_type)

    builder = _DISPATCH.get(product_type)
    if not builder:
        raise ValueError("Unsupported product_type")

    return builder(body, base_kwargs, tx_id)
