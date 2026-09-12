import logging
from datetime import datetime
from hashlib import sha1
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    EquityType,
    GlobalPosition,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.native_entities import TRADING212
from domain.transactions import (
    AccountTx,
    StockTx,
    Transactions,
    TxType,
)
from infrastructure.client.entity.financial.trading212.trading212_client import (
    Trading212Client,
)

_STOCK_TYPES = {"STOCK"}
_ETF_TYPES = {"ETF"}
_EXECUTED_ORDER_STATUSES = {"FILLED", "PARTIALLY_FILLED"}
_SKIPPED_FILL_TYPES = {
    "SPIN_OFF",
    "FOP",
    "FOP_CORRECTION",
    "STOCK_DISTRIBUTION",
    "CUSTOM_STOCK_DISTRIBUTION",
}
_STOCK_DIVIDEND_FILLS = {"STOCK_DIVIDENDS", "SCRIP_STOCK_DIVIDENDS"}
_ACQUISITION_FILLS = {"STOCK_ACQUISITION", "CASH_AND_STOCK_ACQUISITION"}


def _get_ref(kind: str, provider_id: str | int) -> str:
    return sha1(f"trading212-{kind}-{provider_id}".encode("UTF-8")).hexdigest()


def _market_from_id(t212_id: str | None) -> str:
    if not t212_id:
        return ""
    parts = t212_id.split("_")
    if len(parts) >= 3:
        return parts[1]
    return ""


def _symbol_from_id(t212_id: str | None) -> str:
    if not t212_id:
        return ""
    return t212_id.split("_", 1)[0]


def _dezimal(value) -> Dezimal:
    if value is None or value == "":
        return Dezimal(0)
    return Dezimal(str(value))


def _abs(value: Dezimal) -> Dezimal:
    return value if value >= Dezimal(0) else Dezimal(0) - value


class Trading212Fetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = Trading212Client()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials or {}
        return await self._client.setup(
            credentials.get("apiKey"), credentials.get("secretKey")
        )

    async def global_position(self) -> GlobalPosition:
        catalog = await self._instruments_by_id()
        summary = await self._client.get_account_summary()
        positions = await self._client.get_positions()

        products: dict = {}
        account = self._map_cash(summary)
        if account:
            products[ProductType.ACCOUNT] = Accounts([account])

        stocks: list[StockDetail] = []
        for position in positions:
            mapped = self._map_position(position, summary, catalog)
            if mapped:
                stocks.append(mapped)

        if stocks:
            products[ProductType.STOCK_ETF] = StockInvestments(stocks)

        return GlobalPosition(id=uuid4(), entity=TRADING212, products=products)

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        catalog = await self._instruments_by_id()
        investment: list[StockTx] = []
        account: list[AccountTx] = []

        investment.extend(
            await self._collect_order_txs(registered_txs, options, catalog)
        )
        investment.extend(
            await self._collect_dividend_txs(registered_txs, options, catalog)
        )
        account.extend(await self._collect_cash_txs(registered_txs, options))

        return Transactions(investment=investment, account=account)

    async def _safe_instruments(self) -> list[dict]:
        try:
            instruments = await self._client.get_instruments()
            return instruments if isinstance(instruments, list) else []
        except Exception:
            self._log.exception("Failed to fetch Trading 212 instruments")
            return []

    async def _instruments_by_id(self) -> dict[str, dict]:
        instruments = await self._safe_instruments()
        return {
            instrument.get("ticker"): instrument
            for instrument in instruments
            if instrument.get("ticker")
        }

    def _instrument_meta(
        self,
        t212_id: str | None,
        nested: dict | None,
        catalog: dict[str, dict],
    ) -> dict:
        nested = nested or {}
        item = catalog.get(t212_id) or {}
        instrument_type = (item.get("type") or "").upper() or None
        return {
            "type": instrument_type,
            "name": item.get("name") or nested.get("name") or t212_id or "Unknown",
            "isin": item.get("isin") or nested.get("isin") or "",
            "ticker": item.get("shortName")
            or nested.get("shortName")
            or _symbol_from_id(t212_id),
            "market": _market_from_id(t212_id),
        }

    def _map_cash(self, summary: dict) -> Account | None:
        cash = summary.get("cash") or {}
        currency = summary.get("currency")
        if not currency:
            return None
        available = _dezimal(cash.get("availableToTrade"))
        in_pies = _dezimal(cash.get("inPies"))
        reserved = _dezimal(cash.get("reservedForOrders"))
        total = available + in_pies + reserved
        if total == Dezimal(0):
            return None
        return Account(
            id=uuid4(),
            total=round(total, 2),
            currency=currency,
            type=AccountType.BROKERAGE,
            name=str(summary.get("id")) if summary.get("id") is not None else None,
            retained=round(in_pies + reserved, 2),
            source=DataSource.REAL,
        )

    def _map_position(
        self, position: dict, summary: dict, catalog: dict[str, dict]
    ) -> StockDetail | None:
        t212_id = position.get("ticker") or (position.get("instrument") or {}).get(
            "ticker"
        )
        meta = self._instrument_meta(t212_id, position.get("instrument"), catalog)
        instrument_type = meta["type"]
        quantity = _dezimal(position.get("quantity"))
        if quantity == Dezimal(0):
            return None

        wallet = position.get("walletImpact") or {}
        account_currency = wallet.get("currency") or summary.get("currency")
        if not account_currency:
            return None
        market_value = _dezimal(wallet.get("currentValue"))
        initial_investment = _dezimal(wallet.get("totalCost"))
        average_buy_price = _dezimal(position.get("averagePricePaid"))

        if instrument_type in _ETF_TYPES:
            equity_type = EquityType.ETF
        elif instrument_type in _STOCK_TYPES:
            equity_type = EquityType.STOCK
        else:
            self._log.warning(
                "Skipping Trading 212 position type '%s' for ticker '%s'",
                instrument_type,
                t212_id,
            )
            return None

        if not meta["isin"]:
            self._log.warning("Skipping equity position without ISIN: %s", t212_id)
            return None

        return StockDetail(
            id=uuid4(),
            name=meta["name"],
            ticker=meta["ticker"],
            isin=meta["isin"],
            shares=quantity,
            market_value=round(market_value, 4),
            currency=account_currency,
            type=equity_type,
            initial_investment=round(initial_investment, 4),
            average_buy_price=round(average_buy_price, 4),
            market=meta["market"],
            source=DataSource.REAL,
        )

    async def _collect_order_txs(
        self,
        registered_txs: set[str],
        options: FetchOptions,
        catalog: dict[str, dict],
    ) -> list[StockTx]:
        investment: list[StockTx] = []
        async for page in self._client.iter_history_orders():
            known_page = True
            for item in page:
                mapped = self._map_history_order(item, registered_txs, catalog)
                if mapped is None:
                    continue
                known_page = False
                investment.append(mapped)
            if page and known_page and not options.deep:
                break
        return investment

    async def _collect_dividend_txs(
        self,
        registered_txs: set[str],
        options: FetchOptions,
        catalog: dict[str, dict],
    ) -> list[StockTx]:
        txs: list[StockTx] = []
        async for page in self._client.iter_history_dividends():
            known_page = True
            for item in page:
                mapped = self._map_dividend(item, registered_txs, catalog)
                if mapped is None:
                    continue
                known_page = False
                txs.append(mapped)
            if page and known_page and not options.deep:
                break
        return txs

    async def _collect_cash_txs(
        self, registered_txs: set[str], options: FetchOptions
    ) -> list[AccountTx]:
        txs: list[AccountTx] = []
        async for page in self._client.iter_history_transactions():
            known_page = True
            for item in page:
                mapped = self._map_cash_tx(item, registered_txs)
                if mapped is None:
                    continue
                known_page = False
                txs.append(mapped)
            if page and known_page and not options.deep:
                break
        return txs

    def _map_history_order(
        self,
        item: dict,
        registered_txs: set[str],
        catalog: dict[str, dict],
    ) -> StockTx | None:
        order = item.get("order") or {}
        fill = item.get("fill")
        if not isinstance(fill, dict) or not fill:
            return None
        if not fill.get("id") and not fill.get("filledAt"):
            return None

        status = (order.get("status") or "").upper()
        if status and status not in _EXECUTED_ORDER_STATUSES:
            return None

        order_id = order.get("id")
        fill_id = fill.get("id")
        if order_id is None and fill_id is None:
            return None

        fill_type = (fill.get("type") or "TRADE").upper()
        if fill_type in _SKIPPED_FILL_TYPES:
            self._log.info("Skipping Trading 212 fill type %s", fill_type)
            return None

        ref = _get_ref("order", fill_id or order_id)
        if ref in registered_txs:
            return None

        t212_id = order.get("ticker") or (order.get("instrument") or {}).get("ticker")
        meta = self._instrument_meta(t212_id, order.get("instrument"), catalog)
        instrument_type = meta["type"]
        if instrument_type not in _STOCK_TYPES and instrument_type not in _ETF_TYPES:
            return None
        name = meta["name"]
        isin = meta["isin"]
        ticker = meta["ticker"]
        market = meta["market"]
        quantity = _dezimal(fill.get("quantity") or order.get("quantity"))
        price = _dezimal(fill.get("price") or order.get("limitPrice"))
        wallet = fill.get("walletImpact") or {}
        currency = wallet.get("currency") or order.get("currency")
        if not currency:
            return None
        net_value = _dezimal(wallet.get("netValue"))
        fees = self._taxes_total(wallet.get("taxes"))
        date = self._parse_date(fill.get("filledAt") or order.get("createdAt"))
        order_date = self._parse_date(order.get("createdAt"))

        if fill_type == "TRADE":
            side = (order.get("side") or "").upper()
            if side == "SELL" or quantity < Dezimal(0):
                tx_type = TxType.SELL
            else:
                tx_type = TxType.BUY
            amount = (
                _abs(net_value) if net_value != Dezimal(0) else _abs(quantity * price)
            )
            return self._build_investment_tx(
                ref=ref,
                name=name,
                amount=amount,
                currency=currency,
                tx_type=tx_type,
                date=date,
                shares=_abs(quantity),
                price=price,
                fees=fees,
                net_amount=_abs(net_value) if net_value != Dezimal(0) else amount,
                isin=isin,
                ticker=ticker,
                market=market,
                order_date=order_date,
                instrument_type=instrument_type,
            )

        if fill_type in _STOCK_DIVIDEND_FILLS:
            return self._build_investment_tx(
                ref=ref,
                name=name,
                amount=_abs(net_value),
                currency=currency,
                tx_type=TxType.DIVIDEND,
                date=date,
                shares=_abs(quantity),
                price=Dezimal(0),
                fees=fees,
                net_amount=_abs(net_value),
                isin=isin,
                ticker=ticker,
                market=market,
                order_date=order_date,
                instrument_type=instrument_type,
            )

        if fill_type == "EQUITY_RIGHTS":
            return self._build_investment_tx(
                ref=ref,
                name=name,
                amount=Dezimal(0),
                currency=currency,
                tx_type=TxType.RIGHT_ISSUE,
                date=date,
                shares=_abs(quantity),
                price=Dezimal(0),
                fees=Dezimal(0),
                net_amount=Dezimal(0),
                isin=isin,
                ticker=ticker,
                market=market,
                order_date=order_date,
                instrument_type=instrument_type,
            )

        if fill_type == "STOCK_SPLIT" or fill_type in _ACQUISITION_FILLS:
            swap_type = TxType.SWAP_FROM if quantity < Dezimal(0) else TxType.SWAP_TO
            return self._build_investment_tx(
                ref=ref,
                name=name,
                amount=Dezimal(0),
                currency=currency,
                tx_type=swap_type,
                date=date,
                shares=_abs(quantity),
                price=Dezimal(0),
                fees=Dezimal(0),
                net_amount=Dezimal(0),
                isin=isin,
                ticker=ticker,
                market=market,
                order_date=order_date,
                instrument_type=instrument_type,
            )

        self._log.info("Skipping unmapped Trading 212 fill type %s", fill_type)
        return None

    def _map_dividend(
        self,
        item: dict,
        registered_txs: set[str],
        catalog: dict[str, dict],
    ) -> StockTx | None:
        reference = item.get("reference")
        if not reference:
            return None
        ref = _get_ref("dividend", reference)
        if ref in registered_txs:
            return None

        t212_id = item.get("ticker")
        meta = self._instrument_meta(t212_id, item.get("instrument"), catalog)
        instrument_type = meta["type"]
        if instrument_type not in _STOCK_TYPES and instrument_type not in _ETF_TYPES:
            return None
        amount = _abs(_dezimal(item.get("amount")))
        currency = item.get("currency")
        if not currency:
            return None
        quantity = _abs(_dezimal(item.get("quantity")))
        date = self._parse_date(item.get("paidOn"))
        return self._build_investment_tx(
            ref=ref,
            name=meta["name"] or "Dividend",
            amount=amount,
            currency=currency,
            tx_type=TxType.DIVIDEND,
            date=date,
            shares=quantity,
            price=Dezimal(0),
            fees=Dezimal(0),
            net_amount=amount,
            isin=meta["isin"],
            ticker=meta["ticker"],
            market=meta["market"],
            order_date=date,
            instrument_type=instrument_type,
        )

    def _map_cash_tx(self, item: dict, registered_txs: set[str]) -> AccountTx | None:
        reference = item.get("reference")
        if not reference:
            return None
        ref = _get_ref("cash", reference)
        if ref in registered_txs:
            return None

        raw_type = (item.get("type") or "").upper()
        amount = _dezimal(item.get("amount"))
        tx_type = self._map_cash_type(raw_type)
        if not tx_type:
            return None
        currency = item.get("currency")
        if not currency:
            return None

        return AccountTx(
            id=uuid4(),
            ref=ref,
            name=raw_type.replace("_", " ").title(),
            amount=_abs(amount),
            currency=currency,
            type=tx_type,
            date=self._parse_date(item.get("dateTime")),
            entity=TRADING212,
            fees=Dezimal(0),
            retentions=Dezimal(0),
            net_amount=_abs(amount),
            product_type=ProductType.ACCOUNT,
            source=DataSource.REAL,
        )

    @staticmethod
    def _map_cash_type(raw_type: str) -> TxType | None:
        if raw_type == "FEE":
            return TxType.FEE
        if raw_type in {"INTEREST_ON_FREE_CASH", "LENDING_INTEREST"}:
            return TxType.INTEREST
        return None

    def _build_investment_tx(
        self,
        *,
        ref: str,
        name: str,
        amount: Dezimal,
        currency: str,
        tx_type: TxType,
        date: datetime,
        shares: Dezimal,
        price: Dezimal,
        fees: Dezimal,
        net_amount: Dezimal,
        isin: str,
        ticker: str,
        market: str,
        order_date: datetime,
        instrument_type: str | None,
    ) -> StockTx | None:
        if instrument_type not in _STOCK_TYPES and instrument_type not in _ETF_TYPES:
            return None
        equity_type = (
            EquityType.ETF if instrument_type in _ETF_TYPES else EquityType.STOCK
        )
        return StockTx(
            id=uuid4(),
            ref=ref,
            name=name,
            amount=round(amount, 4),
            currency=currency,
            type=tx_type,
            date=date,
            entity=TRADING212,
            shares=shares,
            price=round(price, 4),
            fees=round(fees, 4),
            net_amount=round(net_amount, 4),
            isin=isin or None,
            ticker=ticker or None,
            market=market or None,
            retentions=Dezimal(0),
            order_date=order_date,
            equity_type=equity_type,
            product_type=ProductType.STOCK_ETF,
            source=DataSource.REAL,
        )

    @staticmethod
    def _taxes_total(taxes) -> Dezimal:
        total = Dezimal(0)
        if not taxes:
            return total
        for tax in taxes:
            total += _abs(_dezimal(tax.get("quantity")))
        return total

    @staticmethod
    def _parse_date(value: str | None) -> datetime:
        if not value:
            return datetime.now(tzlocal())
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=tzlocal())
            return parsed.astimezone(tzlocal())
        except ValueError:
            return datetime.now(tzlocal())
