from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
)
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
    FundDetail,
    FundInvestments,
    GlobalPosition,
    ProductType,
)
from domain.native_entities import ING
from domain.transactions import FundTx, StockTx, Transactions, TxType
from infrastructure.client.entity.financial.ing.ing_client import INGAPIClient

CONTRIBUTION_FREQUENCY = {
    "MENSUAL": ContributionFrequency.MONTHLY,
    "BIMESTRAL": ContributionFrequency.BIMONTHLY,
    "TRIMESTRAL": ContributionFrequency.QUARTERLY,
    "CUATRIMESTRAL": ContributionFrequency.EVERY_FOUR_MONTHS,
    "SEMESTRAL": ContributionFrequency.SEMIANNUAL,
    "ANUAL": ContributionFrequency.YEARLY,
}


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


def _map_fund_tran_code(code: str | None) -> TxType | None:
    if not code:
        return None
    c = code.upper()
    if c == "SUSC":
        return TxType.BUY
    if c in {"REIM", "REEM", "REFU"}:
        return TxType.SELL
    if c in {"DIV", "DIVI"}:
        return TxType.DIVIDEND
    return None


class INGFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = INGAPIClient()

        self._market_cache: dict[str, str] = {}

        self._fund_product_code_by_uuid: dict[str, str] = {}
        self._fund_isin_cache: dict[str, str] = {}
        self._fund_product_codes_loaded: bool = False

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

        funds = self._build_funds(products, legacy_by_number)

        product_positions = {}
        if accounts:
            product_positions[ProductType.ACCOUNT] = Accounts(accounts)

        if cards:
            product_positions[ProductType.CARD] = Cards(cards)

        if funds:
            product_positions[ProductType.FUND] = FundInvestments(funds)

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

        investment_txs = self._fetch_broker_txs(products, registered_txs)
        investment_txs += self._fetch_fund_txs(products, registered_txs)

        return Transactions(investment=investment_txs, account=[])

    async def auto_contributions(self) -> AutoContributions:
        position = self._client.get_position()
        products = position.get("products", [])

        periodic_contributions: list[PeriodicContribution] = []
        in_five_years = datetime.now(tzlocal()).date() + timedelta(days=5 * 365)

        fund_products = [p for p in products if p.get("type") == "FUND"]
        for fund in fund_products:
            fund_local_uuid = _get_identifier(fund, "LOCAL_UUID")
            if not fund_local_uuid:
                continue
            orders_resp = (
                self._client.get_orders(
                    product_id=fund_local_uuid,
                    order_status="pending",
                    to_date=in_five_years,
                )
                or {}
            )

            for order in orders_resp.get("elements") or []:
                status = order.get("status") or {}
                if status.get("cod") != "P":
                    continue

                if order.get("orderType") != "subscription":
                    continue

                periodicity_raw = (order.get("periodicity") or "").strip().upper()
                frequency = CONTRIBUTION_FREQUENCY.get(periodicity_raw)
                if not frequency:
                    continue
                since = datetime.strptime(order.get("operationDate"), "%d/%m/%Y").date()

                amount = round(Dezimal(order.get("amount")), 2)
                currency = order.get("currency")

                isin = self._get_fund_isin(fund)
                if not isin:
                    continue

                fund_name = fund.get("commercialName").strip()
                alias = fund_name

                periodic_contributions.append(
                    PeriodicContribution(
                        id=uuid4(),
                        alias=alias,
                        target=isin,
                        target_name=fund_name,
                        target_type=ContributionTargetType.FUND,
                        amount=amount,
                        currency=currency,
                        since=since,
                        until=None,
                        frequency=frequency,
                        active=True,
                        is_real=True,
                    )
                )

        return AutoContributions(periodic=periodic_contributions)

    def _fetch_broker_txs(self, products, registered_txs: set[str]) -> list[StockTx]:
        broker = next((p for p in products if p.get("type") == "BROKER"), None)
        if not broker:
            return []

        broker_id = _get_identifier(broker, "LOCAL_UUID")
        opening_date = _parse_broker_opening_date(broker.get("openingDate"))

        txs = self._fetch_broker_movements(broker_id, opening_date, registered_txs)
        return txs

    def _load_fund_product_codes(self):
        if self._fund_product_codes_loaded:
            return
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        reporting = (
            self._client.get_customer_investment_reporting(
                family="FUNDS", start_date=start_date, end_date=end_date
            )
            or {}
        )
        for entry in reporting.get("funds") or []:
            uuid_val = None
            for ident in entry.get("agreementIdentifiers") or []:
                if ident.get("type") == "UUID":
                    uuid_val = ident.get("value")
                    break
            if not uuid_val:
                continue
            product_code = entry.get("productType")
            if product_code:
                self._fund_product_code_by_uuid[uuid_val] = product_code
        self._fund_product_codes_loaded = True

    def _get_fund_isin(self, fund: dict) -> Optional[str]:
        uuid_val = fund.get("uuid")
        if not uuid_val:
            return fund.get("productNumber")
        if uuid_val in self._fund_isin_cache:
            return self._fund_isin_cache[uuid_val]

        self._load_fund_product_codes()
        product_code = self._fund_product_code_by_uuid.get(uuid_val)
        isin = None
        if product_code:
            details = self._client.get_investment_product_details(product_code)
            isin = next(
                (
                    p.get("value")
                    for p in (details or {}).get("productPropertyList", [])
                    if p.get("code") == "isin"
                ),
                None,
            )
        if not isin:
            return None

        self._fund_isin_cache[uuid_val] = isin

        return isin

    def _fetch_fund_txs(self, products, registered_txs: set[str]) -> list[FundTx]:
        fund_products = [p for p in products if p.get("type") == "FUND"]
        if not fund_products:
            return []

        self._load_fund_product_codes()

        fund_txs: list[FundTx] = []
        for fund in fund_products:
            fund_id = _get_identifier(fund, "LOCAL_UUID")
            if not fund_id:
                continue
            isin = self._get_fund_isin(fund)
            if not isin:
                continue

            from_date = _parse_broker_opening_date(fund.get("openingDate"))
            offset = 0
            limit = 100
            continue_next_page = True
            while continue_next_page:
                resp = self._client.get_movements(
                    fund_id, from_date, offset=offset, limit=limit
                )
                elements = resp.get("elements") or []
                for mv in elements:
                    ref = mv.get("uuid")
                    if not ref:
                        continue
                    if ref in registered_txs:
                        continue_next_page = False
                        continue
                    tx_type = _map_fund_tran_code(mv.get("tranCode"))
                    if not tx_type:
                        continue

                    date_dt = _parse_date(mv.get("operationDate") or mv.get("vlpDate"))
                    order_date = date_dt
                    gross_amount = Dezimal(mv.get("amount") or 0)
                    net_amount = gross_amount
                    fees = Dezimal(0)
                    retentions = Dezimal(0)
                    shares_val = Dezimal(mv.get("sharesNumbers") or 0)
                    price_val = Dezimal(mv.get("vlp") or 0)
                    currency = mv.get("currency") or fund.get("denominationCurrency")
                    name = f"{mv.get('description')} {fund.get('commercialName')}"
                    fund_txs.append(
                        FundTx(
                            id=uuid4(),
                            ref=str(ref),
                            name=name.strip(),
                            amount=round(gross_amount, 4),
                            net_amount=round(net_amount, 4),
                            currency=currency,
                            type=tx_type,
                            order_date=order_date,
                            entity=ING,
                            isin=isin,
                            shares=shares_val,
                            price=price_val,
                            market="",
                            fees=fees,
                            retentions=retentions,
                            date=date_dt,
                            product_type=ProductType.FUND,
                            is_real=True,
                        )
                    )
                count = resp.get("count") or len(elements)
                total = resp.get("total") or 0
                offset += limit
                if count == 0 or (total and offset >= total) or not continue_next_page:
                    break
        return fund_txs

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

    def _build_funds(
        self, products: list[dict], legacy_by_number: dict[str, dict]
    ) -> list[FundDetail]:
        self._load_fund_product_codes()
        funds: list[FundDetail] = []
        for prod in products:
            if prod.get("type") != "FUND":
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

            isin = self._get_fund_isin(prod)
            if not isin:
                continue

            name = prod.get("commercialName") or legacy.get("name")
            shares = Dezimal(legacy.get("numberOfShares"))
            initial_investment = Dezimal(legacy.get("investment"))
            market_value = Dezimal(legacy.get("assessment"))
            currency = legacy.get("currency") or prod.get("denominationCurrency")
            average_buy_price = (
                initial_investment / shares if shares > 0 else Dezimal(0)
            )
            fund = FundDetail(
                id=uuid4(),
                name=name,
                isin=isin,
                market=None,
                shares=shares,
                initial_investment=round(initial_investment, 4),
                average_buy_price=round(average_buy_price, 4),
                market_value=round(market_value, 4),
                currency=currency,
                portfolio=None,
            )
            funds.append(fund)

        return funds
