import logging
from datetime import date, datetime
from hashlib import sha1
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity_login import (
    EntityLoginParams,
    EntityLoginResult,
    LoginResultCode,
)
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    EquityType,
    FundDetail,
    FundInvestments,
    FundType,
    GlobalPosition,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.native_entities import DEGIRO
from domain.transactions import (
    AccountTx,
    FundTx,
    StockTx,
    Transactions,
    TxType,
)
from infrastructure.client.entity.financial.degiro.degiro_client import DegiroClient

PRODUCT_TYPE_STOCK = "STOCK"
PRODUCT_TYPE_ETF = "ETF"
PRODUCT_TYPE_FUND = "FUND"


def _extract_position_fields(position_values: list[dict]) -> dict:
    fields = {}
    for item in position_values:
        name = item.get("name")
        value = item.get("value")
        if name:
            fields[name] = value
    return fields


def _get_ref(tx_id: str | int) -> str:
    return sha1(f"degiro-{tx_id}".encode("UTF-8")).hexdigest()


class DegiroFetcher(FinancialEntityFetcher):
    def __init__(self) -> None:
        self._client = DegiroClient()
        self._log = logging.getLogger(__name__)

    def cancel_login(self) -> None:
        self._client.cancel_login()

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        two_factor = login_params.two_factor
        session = login_params.session

        if session and not login_params.options.force_new_session:
            restored = self._client.restore_session(session)
            if restored:
                return EntityLoginResult(LoginResultCode.RESUMED)

        if two_factor and two_factor.process_id:
            return await self._client.complete_login(two_factor.process_id)

        username = credentials["user"]
        password = credentials["password"]
        totp_secret = credentials.get("totp_secret")
        one_time_password = None
        if two_factor and two_factor.code:
            try:
                one_time_password = int(two_factor.code)
            except (ValueError, TypeError):
                pass

        return await self._client.login(
            username=username,
            password=password,
            totp_secret=totp_secret,
            one_time_password=one_time_password,
        )

    async def global_position(self) -> GlobalPosition:
        raw_portfolio = await self._client.get_portfolio()
        raw_totals = await self._client.get_total_portfolio()

        positions = self._parse_portfolio_positions(raw_portfolio)
        product_ids = [p["id"] for p in positions if p.get("id")]
        products_info = await self._client.get_products_info(product_ids)
        products_data = products_info.get("data", {}) if products_info else {}

        accounts = self._map_cash_positions(raw_totals)

        stocks: list[StockDetail] = []
        funds: list[FundDetail] = []

        for position in positions:
            product_id = position.get("id")
            if not product_id:
                continue

            size = position.get("size", 0)
            if size == 0:
                continue

            product_info = products_data.get(str(product_id), {})
            investment = self._map_investment(position, product_info)
            if isinstance(investment, StockDetail):
                stocks.append(investment)
            elif isinstance(investment, FundDetail):
                funds.append(investment)

        products: dict = {ProductType.ACCOUNT: Accounts(accounts)}
        if stocks:
            products[ProductType.STOCK_ETF] = StockInvestments(stocks)
        if funds:
            products[ProductType.FUND] = FundInvestments(funds)

        return GlobalPosition(id=uuid4(), entity=DEGIRO, products=products)

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        to_date = date.today()
        from_date = to_date.replace(year=to_date.year - 5, day=min(to_date.day, 28))

        raw_txs = await self._client.get_transactions_history(from_date, to_date)
        raw_cash_movements = await self._client.get_account_overview(from_date, to_date)

        tx_product_ids = {tx["productId"] for tx in raw_txs if tx.get("productId")}
        products_info = await self._client.get_products_info(list(tx_product_ids))
        products_data = products_info.get("data", {}) if products_info else {}

        investment_txs: list[StockTx | FundTx] = []
        account_txs: list[AccountTx] = []

        for raw_tx in raw_txs:
            tx_id = raw_tx.get("id")
            if tx_id is None:
                continue

            ref = _get_ref(tx_id)
            if ref in registered_txs:
                continue

            product_id = raw_tx.get("productId")
            product_info = products_data.get(str(product_id), {}) if product_id else {}

            mapped_tx = self._map_trade_tx(raw_tx, ref, product_info)
            if mapped_tx:
                investment_txs.append(mapped_tx)

        for movement in raw_cash_movements:
            movement_id = movement.get("id")
            if movement_id is None:
                continue

            ref = _get_ref(f"cash-{movement_id}")
            if ref in registered_txs:
                continue

            mapped_tx = self._map_cash_movement(movement, ref)
            if mapped_tx:
                account_txs.append(mapped_tx)

        return Transactions(investment=investment_txs, account=account_txs)

    @staticmethod
    def _parse_portfolio_positions(raw_portfolio: dict | None) -> list[dict]:
        if not raw_portfolio:
            return []

        portfolio = raw_portfolio.get("portfolio", {})
        raw_values = portfolio.get("value", [])

        positions = []
        for entry in raw_values:
            entry_values = entry.get("value", [])
            fields = _extract_position_fields(entry_values)
            if fields.get("id"):
                positions.append(fields)

        return positions

    @staticmethod
    def _map_cash_positions(raw_totals: dict | None) -> list[Account]:
        if not raw_totals:
            return []

        accounts = []
        cash_funds = raw_totals.get("cashFunds", {})
        cash_entries = cash_funds.get("value", [])

        for entry in cash_entries:
            entry_values = entry.get("value", [])
            fields = _extract_position_fields(entry_values)

            currency = fields.get("currencyCode")
            value = fields.get("value")
            if currency and value is not None:
                amount = Dezimal(str(value))
                if amount == Dezimal(0):
                    continue
                accounts.append(
                    Account(
                        id=uuid4(),
                        total=round(amount, 2),
                        currency=currency,
                        type=AccountType.BROKERAGE,
                    )
                )

        return accounts

    def _map_investment(
        self, position: dict, product_info: dict
    ) -> StockDetail | FundDetail | None:
        product_type = product_info.get("productType", "").upper()
        isin = product_info.get("isin", "")
        name = product_info.get("name", "Unknown")
        symbol = product_info.get("symbol", "")
        currency = product_info.get("currency", "EUR")

        size = Dezimal(str(position.get("size", 0)))
        price = Dezimal(str(position.get("price", 0)))
        value = Dezimal(str(position.get("value", 0)))
        break_even_price = position.get("breakEvenPrice")

        average_buy_price = (
            Dezimal(str(break_even_price)) if break_even_price is not None else None
        )
        initial_investment = (
            round(average_buy_price * size, 2)
            if average_buy_price is not None and size != 0
            else None
        )

        market_value = round(value, 2) if value else round(price * size, 2)

        if product_type in (PRODUCT_TYPE_STOCK, PRODUCT_TYPE_ETF):
            equity_type = (
                EquityType.ETF if product_type == PRODUCT_TYPE_ETF else EquityType.STOCK
            )
            return StockDetail(
                id=uuid4(),
                name=name,
                ticker=symbol,
                isin=isin,
                shares=size,
                market_value=market_value,
                currency=currency,
                type=equity_type,
                initial_investment=initial_investment,
                average_buy_price=average_buy_price,
                source=DataSource.REAL,
            )
        elif product_type == PRODUCT_TYPE_FUND:
            return FundDetail(
                id=uuid4(),
                name=name,
                isin=isin,
                market=None,
                shares=size,
                market_value=market_value,
                currency=currency,
                type=FundType.MUTUAL_FUND,
                initial_investment=initial_investment,
                average_buy_price=average_buy_price,
                source=DataSource.REAL,
            )
        else:
            # Treat unknown product types as stocks
            if isin:
                return StockDetail(
                    id=uuid4(),
                    name=name,
                    ticker=symbol,
                    isin=isin,
                    shares=size,
                    market_value=market_value,
                    currency=currency,
                    type=EquityType.STOCK,
                    initial_investment=initial_investment,
                    average_buy_price=average_buy_price,
                    source=DataSource.REAL,
                )
            self._log.warning(
                "Skipping unknown Degiro product type '%s' for product '%s'",
                product_type,
                name,
            )
            return None

    def _map_trade_tx(
        self, raw_tx: dict, ref: str, product_info: dict
    ) -> StockTx | FundTx | None:
        buysell = raw_tx.get("buysell", "")
        if buysell == "B":
            tx_type = TxType.BUY
        elif buysell == "S":
            tx_type = TxType.SELL
        else:
            return None

        tx_date_str = raw_tx.get("date")
        if not tx_date_str:
            return None

        if isinstance(tx_date_str, str):
            try:
                tx_date = datetime.fromisoformat(tx_date_str).replace(tzinfo=tzlocal())
            except ValueError:
                self._log.warning("Could not parse transaction date: %s", tx_date_str)
                return None
        elif isinstance(tx_date_str, datetime):
            tx_date = (
                tx_date_str.replace(tzinfo=tzlocal())
                if tx_date_str.tzinfo is None
                else tx_date_str
            )
        else:
            return None

        quantity = Dezimal(str(raw_tx.get("quantity", 0)))
        price = Dezimal(str(raw_tx.get("price", 0)))
        total = abs(Dezimal(str(raw_tx.get("total", 0))))
        fee = abs(Dezimal(str(raw_tx.get("feeInBaseCurrency", 0))))
        total_plus_fee = abs(Dezimal(str(raw_tx.get("totalPlusFeeInBaseCurrency", 0))))

        isin = product_info.get("isin", "")
        name = product_info.get("name", "Unknown")
        symbol = product_info.get("symbol", "")
        currency = product_info.get("currency", "EUR")
        product_type = product_info.get("productType", "").upper()

        amount = total_plus_fee if total_plus_fee else total + fee

        if product_type == PRODUCT_TYPE_FUND:
            return FundTx(
                id=uuid4(),
                ref=ref,
                name=name,
                amount=amount,
                currency=currency,
                type=tx_type,
                date=tx_date,
                entity=DEGIRO,
                shares=quantity,
                price=price,
                fees=fee,
                net_amount=total,
                isin=isin,
                retentions=Dezimal(0),
                fund_type=FundType.MUTUAL_FUND,
                product_type=ProductType.FUND,
                source=DataSource.REAL,
            )

        equity_type = (
            EquityType.ETF if product_type == PRODUCT_TYPE_ETF else EquityType.STOCK
        )
        return StockTx(
            id=uuid4(),
            ref=ref,
            name=name,
            amount=amount,
            currency=currency,
            type=tx_type,
            date=tx_date,
            entity=DEGIRO,
            shares=quantity,
            price=price,
            fees=fee,
            net_amount=total,
            isin=isin,
            ticker=symbol,
            retentions=Dezimal(0),
            equity_type=equity_type,
            product_type=ProductType.STOCK_ETF,
            source=DataSource.REAL,
        )

    @staticmethod
    def _map_cash_movement(movement: dict, ref: str) -> AccountTx | None:
        movement_type = (movement.get("type") or "").upper()
        description = movement.get("description", "")

        if movement_type in ("CASH_TRANSACTION", "CASH_FUND_TRANSACTION"):
            return None

        if "INTEREST" in movement_type or "interest" in description.lower():
            tx_type = TxType.INTEREST
        elif "DIVIDEND" in movement_type or "dividend" in description.lower():
            tx_type = TxType.DIVIDEND
        elif "FEE" in movement_type or "fee" in description.lower():
            tx_type = TxType.FEE
        else:
            return None

        change = movement.get("change")
        if change is None:
            return None

        amount = round(Dezimal(str(change)), 2)
        currency = movement.get("currency", "EUR")

        tx_date_raw = movement.get("date")
        if not tx_date_raw:
            return None

        if isinstance(tx_date_raw, str):
            try:
                tx_date = datetime.fromisoformat(tx_date_raw).replace(tzinfo=tzlocal())
            except ValueError:
                return None
        elif isinstance(tx_date_raw, datetime):
            tx_date = (
                tx_date_raw.replace(tzinfo=tzlocal())
                if tx_date_raw.tzinfo is None
                else tx_date_raw
            )
        else:
            return None

        return AccountTx(
            id=uuid4(),
            ref=ref,
            name=description or movement_type,
            amount=abs(amount),
            currency=currency,
            type=tx_type,
            date=tx_date,
            entity=DEGIRO,
            fees=Dezimal(0),
            retentions=Dezimal(0),
            product_type=ProductType.ACCOUNT,
            source=DataSource.REAL,
        )
