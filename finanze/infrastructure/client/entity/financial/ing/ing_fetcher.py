from datetime import datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    GlobalPosition,
    ProductType,
)
from domain.native_entities import ING
from domain.transactions import StockTx, Transactions, TxType
from infrastructure.client.entity.financial.ing.ing_client import INGAPIClient


def _map_op_type(raw: str | None, stock_type: str | None) -> TxType | None:
    if raw == "C":
        return TxType.BUY
    if raw == "V":
        return TxType.RIGHT_SELL if stock_type == "D" else TxType.SELL
    if raw == "DV":
        return TxType.DIVIDEND
    if raw == "GD":
        return TxType.RIGHT_ISSUE
    if raw == "AC":
        return TxType.SWAP_TO
    if raw == "BC":
        return TxType.SWAP_FROM
    return None


def _parse_date(date_str: str | None) -> datetime:
    if not date_str:
        return datetime.now(tzlocal())
    try:
        if " " in date_str:
            return datetime.strptime(date_str, "%d/%m/%Y %H:%M").replace(
                tzinfo=tzlocal()
            )
        return datetime.strptime(date_str, "%d/%m/%Y").replace(tzinfo=tzlocal())
    except Exception:
        return datetime.now(tzlocal())


def _parse_broker_opening_date(opening_date_str: str | None):
    if not opening_date_str:
        return datetime(2018, 1, 1).date()
    try:
        return datetime.strptime(opening_date_str, "%Y-%m-%d").date()
    except Exception:
        return datetime(2018, 1, 1).date()


def _map_movement_to_stock_tx(
    mv: dict, market_name: str | None = None
) -> StockTx | None:
    ref = mv.get("uuid")
    if not ref:
        return None

    tx_type = _map_op_type(mv.get("operationType"), mv.get("stockType"))
    if not tx_type:
        return None

    isin = mv.get("stockName")
    shares = mv.get("titlesNumber")
    price = mv.get("operationChange")
    market = market_name or mv.get("marketCode")
    currency = mv.get("currency")
    name = (mv.get("stockDescription") or "").strip()
    ticker = mv.get("stockShortName")

    date_dt = _parse_date(mv.get("effectiveDate"))

    if tx_type in (TxType.BUY, TxType.SELL, TxType.RIGHT_SELL):
        gross = Dezimal(mv.get("operationAmount") or mv.get("amount") or 0)
        net = Dezimal(mv.get("netAmount") or 0)
        fees = Dezimal(mv.get("commission") or 0)
        retentions = Dezimal(mv.get("retentionTo") or 0)
    elif tx_type == TxType.DIVIDEND:
        gross = Dezimal(mv.get("grossAmount") or 0)
        net = Dezimal(mv.get("netAmount") or 0)
        fees = Dezimal(0)
        retentions = Dezimal(mv.get("retentionTo") or 0)
    else:  # RIGHT_ISSUE, SWAP_TO, SWAP_FROM and other zero-amount ops
        gross = Dezimal(0)
        net = Dezimal(0)
        fees = Dezimal(0)
        retentions = Dezimal(0)

    try:
        shares_val = round(Dezimal(shares or 0), 4)
    except Exception:
        shares_val = Dezimal(0)
    try:
        price_val = round(Dezimal(price or 0), 4)
    except Exception:
        price_val = Dezimal(0)

    return StockTx(
        id=uuid4(),
        ref=str(ref),
        name=name,
        ticker=ticker,
        amount=round(gross, 2),
        net_amount=round(net, 2),
        currency=currency,
        type=tx_type,
        order_date=date_dt,
        entity=ING,
        isin=isin,
        shares=shares_val,
        price=price_val,
        market=market,
        fees=round(fees, 2),
        retentions=round(retentions, 2),
        date=date_dt,
        product_type=ProductType.STOCK_ETF,
        is_real=True,
        linked_tx=None,
    )


def _get_identifier(entry: dict, id_type: str) -> str | None:
    for ident in entry.get("identifiers", []) or []:
        if ident.get("type") == id_type:
            return ident.get("value")
    return None


def _legacy_by_product_number(legacy_products: list[dict]) -> dict[str, dict]:
    return {
        lp.get("productNumber"): lp
        for lp in (legacy_products or [])
        if lp.get("productNumber")
    }


def _build_accounts(
    products: list[dict], legacy_by_number: dict[str, dict]
) -> tuple[list[Account], dict[str, Account]]:
    accounts: list[Account] = []
    accounts_by_number: dict[str, Account] = {}

    for prod in products:
        prod_type = prod.get("type")
        if prod_type not in ("CURRENT_ACCOUNT", "SAVINGS_ACCOUNT"):
            continue

        suspended = False
        for st in prod.get("statuses", []) or []:
            if st.get("type") == "PRODUCT_STATUS" and st.get("value") != "EFF_AR":
                suspended = True
                break

        if suspended:
            continue

        product_number = _get_identifier(prod, "PRODUCT_NUMBER")
        legacy = legacy_by_number.get(product_number, {})

        acc_type = (
            AccountType.SAVINGS
            if prod_type == "SAVINGS_ACCOUNT"
            else AccountType.CHECKING
        )

        name = (
            legacy.get("alias")
            or prod.get("nickName")
            or legacy.get("name")
            or prod.get("commercialName")
        )

        iban = legacy.get("iban") or _get_identifier(prod, "IBAN")
        iban = iban.replace(" ", "") if iban else None

        balance = legacy.get("balance")
        if balance is None:
            balance = prod.get("balanceToShow", 0)
        currency = legacy.get("currency") or prod.get("denominationCurrency")

        interest = None
        tae = legacy.get("tae")
        if tae is not None:
            interest = round(Dezimal(tae) / 100, 4)

        account_obj = Account(
            id=uuid4(),
            total=round(Dezimal(balance), 2),
            currency=currency,
            name=name,
            iban=iban,
            type=acc_type,
            interest=interest,
        )

        accounts.append(account_obj)
        if product_number:
            accounts_by_number[product_number] = account_obj

    return accounts, accounts_by_number


def _mark_brokerage_account(
    products: list[dict],
    legacy_by_number: dict[str, dict],
    accounts_by_number: dict[str, Account],
) -> None:
    broker_product_number = None
    for prod in products:
        if prod.get("type") == "BROKER":
            pn = _get_identifier(prod, "PRODUCT_NUMBER")
            legacy = legacy_by_number.get(pn)
            if legacy and legacy.get("associatedAccount"):
                broker_product_number = legacy["associatedAccount"].get("productNumber")
                break

    if broker_product_number and broker_product_number in accounts_by_number:
        accounts_by_number[broker_product_number].type = AccountType.BROKERAGE


def _build_cards(
    products: list[dict],
    legacy_by_number: dict[str, dict],
    accounts_by_number: dict[str, Account],
) -> list[Card]:
    cards: list[Card] = []
    for prod in products:
        if prod.get("type") not in ("DEBIT_CARD", "CREDIT_CARD"):
            continue

        product_number = _get_identifier(prod, "PRODUCT_NUMBER")
        associated_account_number = _get_identifier(prod, "ASSOCIATED_ACCOUNT")
        related_account_id = (
            accounts_by_number[associated_account_number].id
            if associated_account_number in accounts_by_number
            else None
        )

        suspended = False
        active = False
        for st in prod.get("statuses", []) or []:
            if st.get("type") == "PRODUCT_STATUS" and st.get("value") != "EFF_AR":
                suspended = True
                break

            if st.get("type") == "CARD_STATUS":
                active = st.get("value") == "ON"
                break

        if suspended:
            continue

        card_type = (
            CardType.DEBIT if prod.get("type") == "DEBIT_CARD" else CardType.CREDIT
        )
        ending = product_number[-4:] if product_number else None
        currency = prod.get("denominationCurrency")

        legacy = legacy_by_number.get(product_number, {})
        limit_val = legacy.get("creditLimit")
        available_credit = legacy.get("availableCreditAmount")

        limit = None
        used = Dezimal(0)
        if limit_val is not None:
            try:
                limit = Dezimal(limit_val)
            except Exception:
                limit = None
        if limit is not None and available_credit is not None:
            try:
                used = round(limit - Dezimal(available_credit), 2)
            except Exception:
                used = Dezimal(0)

        cards.append(
            Card(
                id=uuid4(),
                name=prod.get("nickName") or prod.get("commercialName"),
                ending=ending,
                currency=currency,
                type=card_type,
                limit=limit,
                used=used,
                active=active,
                related_account=related_account_id,
            )
        )

    return cards


class INGFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = INGAPIClient()
        # Cache for market code -> human-readable name (e.g., "000" -> "M.CONTINUO")
        self._market_cache: dict[str, str] = {}

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        return self._client.complete_login(
            login_params.credentials, login_params.options, login_params.session
        )

    async def global_position(self) -> GlobalPosition:
        position = self._client.get_position()
        products = position.get("products", [])
        legacy_products = position.get("legacyProducts", [])

        legacy_by_number = _legacy_by_product_number(legacy_products)
        accounts, accounts_by_number = _build_accounts(products, legacy_by_number)
        _mark_brokerage_account(products, legacy_by_number, accounts_by_number)
        cards = _build_cards(products, legacy_by_number, accounts_by_number)

        product_positions = {
            ProductType.ACCOUNT: Accounts(accounts),
            ProductType.CARD: Cards(cards),
        }

        return GlobalPosition(
            id=uuid4(),
            entity=ING,
            products=product_positions,
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        position = self._client.get_position()
        products = position.get("products", [])

        broker = next((p for p in products if p.get("type") == "BROKER"), None)
        if not broker:
            return Transactions(investment=[], account=[])

        broker_id = _get_identifier(broker, "LOCAL_UUID") or broker.get("uuid")
        opening_date = _parse_broker_opening_date(broker.get("openingDate"))

        txs = self._fetch_broker_movements(broker_id, opening_date, registered_txs)
        return Transactions(investment=txs, account=[])

    def _resolve_market_name(
        self, market_code: str | None, order_id: str | None
    ) -> str | None:
        if not market_code:
            return None
        cached = self._market_cache.get(market_code)
        if cached:
            return cached
        if not order_id or str(order_id).strip() in {"", "-"}:
            return market_code
        try:
            detail = self._client.get_broker_order(market_code, str(order_id))
            desc = ((detail.get("market") or {}).get("description") or {}).get(
                "description"
            )
            if isinstance(desc, str) and desc.strip():
                self._market_cache[market_code] = desc
                return desc
        except Exception:
            pass
        return market_code

    def _fetch_broker_movements(
        self, broker_id: str, from_date, registered_txs: set[str]
    ) -> list[StockTx]:
        all_elements: list[StockTx] = []
        offset = 0
        limit = 100
        continue_next_page = True

        while continue_next_page:
            resp = self._client.get_movements(
                broker_id, from_date, offset=offset, limit=limit
            )
            elements = resp.get("elements") or []
            for mv in elements:
                market_name = self._resolve_market_name(
                    mv.get("marketCode"), mv.get("idOrder")
                )
                tx = _map_movement_to_stock_tx(mv, market_name)
                if tx:
                    if tx.ref in registered_txs:
                        continue_next_page = False
                        continue
                    all_elements.append(tx)

            count = resp.get("count") or len(elements)
            total = resp.get("total") or len(elements)
            offset += limit
            if len(all_elements) >= total or count == 0:
                break

        return all_elements
