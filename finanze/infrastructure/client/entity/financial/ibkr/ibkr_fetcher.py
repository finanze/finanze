import csv
import hashlib
import io
import logging
from datetime import datetime, date, timedelta
from typing import Optional
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
from domain.native_entities import IBKR
from domain.transactions import AccountTx, StockTx, Transactions, TxType
from infrastructure.client.entity.financial.ibkr.ibkr_client import IBKRClient

INITIAL_FETCH_YEARS = 5


def _tx_ref(date_str: str, symbol: str, qty: str, price: str, currency: str) -> str:
    raw = f"ibkr-{date_str}-{symbol}-{qty}-{price}-{currency}"
    return hashlib.sha1(raw.encode()).hexdigest()


class IBKRFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = IBKRClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        return await self._client.complete_login(
            login_params.credentials, login_params.options, login_params.session
        )

    async def global_position(self) -> GlobalPosition:
        account_id = self._client.account_id
        if not account_id:
            return GlobalPosition(id=uuid4(), entity=IBKR, products={})

        ledger = await self._client.get_ledger(account_id)
        positions = await self._client.get_positions(account_id)

        accounts = self._build_accounts(ledger)
        stocks = await self._build_stocks(positions)

        product_positions = {}
        if accounts:
            product_positions[ProductType.ACCOUNT] = Accounts(accounts)
        if stocks:
            product_positions[ProductType.STOCK_ETF] = StockInvestments(stocks)

        return GlobalPosition(id=uuid4(), entity=IBKR, products=product_positions)

    def _build_accounts(self, ledger: list[dict]) -> list[Account]:
        accounts = []
        for entry in ledger:
            key = entry.get("key", "")
            if not key.startswith("LedgerList") or key == "LedgerListBASE":
                continue

            currency = entry.get("secondKey")
            if not currency:
                continue

            cash_balance = Dezimal(entry.get("cashbalance", 0))
            accounts.append(
                Account(
                    id=uuid4(),
                    total=round(cash_balance, 2),
                    currency=currency,
                    name=f"IBKR {currency}",
                    type=AccountType.BROKERAGE,
                )
            )
        return accounts

    async def _build_stocks(self, positions: list[dict]) -> list[StockDetail]:
        if not positions:
            return []

        conids = [p.get("conid") for p in positions if p.get("conid")]
        secdef_map: dict[int, dict] = {}
        if conids:
            secdefs = await self._client.get_secdef(conids)
            for sd in secdefs:
                secdef_map[sd.get("conid")] = sd

        stocks = []
        for pos in positions:
            sec_type = pos.get("secType", "")
            if sec_type != "STK":
                continue

            conid = pos.get("conid")
            shares = Dezimal(pos.get("position", 0))
            if shares == 0:
                continue

            avg_price = Dezimal(pos.get("avgPrice", 0))
            market_value = Dezimal(pos.get("marketValue", 0))
            currency = pos.get("currency", "")
            description = pos.get("description", "")

            sd = secdef_map.get(conid, {})
            ticker = sd.get("ticker") or description
            name = sd.get("name") or sd.get("fullName") or description
            exchange = sd.get("listingExchange", "")

            initial_investment = shares * avg_price

            stocks.append(
                StockDetail(
                    id=uuid4(),
                    name=name,
                    ticker=ticker,
                    isin=ticker,
                    shares=round(shares, 4),
                    initial_investment=round(initial_investment, 4),
                    average_buy_price=round(avg_price, 4),
                    market_value=round(abs(market_value), 4),
                    currency=currency,
                    type=EquityType.STOCK,
                    market=exchange,
                )
            )
        return stocks

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        to_date = date.today()
        all_isin_map: dict[str, str] = {}
        all_investment_txs: list[StockTx] = []
        all_account_txs: list[AccountTx] = []

        # Statements API supports max 365 days per request; loop in yearly chunks
        for year_offset in range(INITIAL_FETCH_YEARS):
            chunk_to = to_date - timedelta(days=year_offset * 365)
            chunk_from = chunk_to - timedelta(days=365)

            csv_text = await self._client.download_activity_statement(
                chunk_from, chunk_to
            )
            if not csv_text:
                break

            all_isin_map.update(_parse_financial_instrument_info(csv_text))
            chunk_trades = _parse_trades(csv_text, all_isin_map, registered_txs)
            chunk_account = _parse_deposits_and_interest(csv_text, registered_txs)
            if not chunk_trades and not chunk_account and year_offset > 0:
                break
            all_investment_txs.extend(chunk_trades)
            all_account_txs.extend(chunk_account)

        return Transactions(investment=all_investment_txs, account=all_account_txs)


def _parse_financial_instrument_info(csv_text: str) -> dict[str, str]:
    """Parse the Financial Instrument Information section to map symbols to ISINs."""
    isin_map: dict[str, str] = {}
    reader = csv.reader(io.StringIO(csv_text))
    header: Optional[list[str]] = None

    for row in reader:
        if len(row) < 3:
            continue
        section = row[0].strip()
        if section != "Financial Instrument Information":
            header = None
            continue

        row_type = row[1].strip()
        if row_type == "Header":
            header = [h.strip() for h in row[2:]]
            continue
        if row_type != "Data" or not header:
            continue

        fields = dict(zip(header, row[2:]))
        symbol = fields.get("Symbol", "").strip()
        security_id = fields.get("Security ID", "").strip()
        if symbol and security_id:
            isin_map[symbol] = security_id

    return isin_map


def _parse_trades(
    csv_text: str,
    isin_map: dict[str, str],
    registered_txs: set[str],
) -> list[StockTx]:
    txs: list[StockTx] = []
    reader = csv.reader(io.StringIO(csv_text))
    header: Optional[list[str]] = None

    for row in reader:
        if len(row) < 3:
            continue
        section = row[0].strip()
        if section != "Trades":
            header = None
            continue

        row_type = row[1].strip()
        if row_type == "Header":
            header = [h.strip() for h in row[2:]]
            continue
        if row_type != "Data" or not header:
            continue

        fields = dict(zip(header, row[2:]))
        discriminator = fields.get("DataDiscriminator", "").strip()
        if discriminator != "Order":
            continue

        asset_category = fields.get("Asset Category", "").strip()
        if asset_category != "Stocks":
            continue

        tx = _map_trade(fields, isin_map, registered_txs)
        if tx:
            txs.append(tx)

    return txs


def _map_trade(
    fields: dict,
    isin_map: dict[str, str],
    registered_txs: set[str],
) -> Optional[StockTx]:
    symbol = fields.get("Symbol", "").strip()
    if not symbol:
        return None

    qty_str = fields.get("Quantity", "").strip().replace(",", "")
    try:
        qty = Dezimal(qty_str)
    except Exception:
        return None

    if qty > 0:
        tx_type = TxType.BUY
    elif qty < 0:
        tx_type = TxType.SELL
    else:
        return None

    currency = fields.get("Currency", "").strip()
    date_str = fields.get("Date/Time", "").strip()
    price_str = fields.get("T. Price", "").strip().replace(",", "")
    proceeds_str = fields.get("Proceeds", "").strip().replace(",", "")
    commission_str = fields.get("Comm/Fee", "").strip().replace(",", "")

    ref = _tx_ref(date_str, symbol, qty_str, price_str, currency)
    if ref in registered_txs:
        return None

    try:
        tx_date = datetime.strptime(date_str, "%Y-%m-%d, %H:%M:%S").replace(
            tzinfo=tzlocal()
        )
    except ValueError, TypeError:
        return None

    shares = abs(qty)
    try:
        price = abs(Dezimal(price_str))
    except Exception:
        price = Dezimal(0)

    amount = price * shares

    try:
        fees = abs(Dezimal(commission_str))
    except Exception:
        fees = Dezimal(0)

    try:
        proceeds = abs(Dezimal(proceeds_str))
    except Exception:
        proceeds = amount

    net_amount = proceeds + fees if tx_type == TxType.BUY else proceeds

    isin = isin_map.get(symbol)

    return StockTx(
        id=uuid4(),
        ref=ref,
        name=symbol,
        ticker=symbol,
        amount=round(amount, 2),
        net_amount=round(net_amount, 2),
        currency=currency,
        type=tx_type,
        order_date=tx_date,
        entity=IBKR,
        isin=isin,
        shares=round(shares, 4),
        price=round(price, 4),
        market=None,
        fees=round(fees, 2),
        retentions=Dezimal(0),
        date=tx_date,
        product_type=ProductType.STOCK_ETF,
        source=DataSource.REAL,
        linked_tx=None,
        equity_type=EquityType.STOCK,
    )


_ACCOUNT_TX_SECTIONS = {
    "Deposits & Withdrawals": {
        "date_field": "Settle Date",
        "type_fn": lambda desc, amt: (
            TxType.TRANSFER_IN if amt > 0 else TxType.TRANSFER_OUT
        ),
    },
    "Interest": {
        "date_field": "Date",
        "type_fn": lambda desc, amt: TxType.INTEREST,
    },
}


def _parse_deposits_and_interest(
    csv_text: str, registered_txs: set[str]
) -> list[AccountTx]:
    txs: list[AccountTx] = []
    reader = csv.reader(io.StringIO(csv_text))
    header: Optional[list[str]] = None
    current_section: Optional[str] = None

    for row in reader:
        if len(row) < 3:
            continue

        section = row[0].strip()
        row_type = row[1].strip()

        if section in _ACCOUNT_TX_SECTIONS:
            if section != current_section:
                current_section = section
                header = None
            if row_type == "Header":
                header = [h.strip() for h in row[2:]]
                continue
            if row_type not in ("Data", "Total") or not header:
                continue
            if row_type == "Total":
                continue
        else:
            if current_section:
                current_section = None
                header = None
            continue

        fields = dict(zip(header, row[2:]))
        tx = _map_account_tx(fields, current_section, registered_txs)
        if tx:
            txs.append(tx)

    return txs


def _map_account_tx(
    fields: dict,
    section: str,
    registered_txs: set[str],
) -> Optional[AccountTx]:
    section_config = _ACCOUNT_TX_SECTIONS[section]

    currency = fields.get("Currency", "").strip()
    if not currency:
        return None

    date_str = fields.get(section_config["date_field"], "").strip()
    description = fields.get("Description", "").strip()
    amount_str = fields.get("Amount", "").strip().replace(",", "")

    try:
        amount = Dezimal(amount_str)
    except Exception:
        return None

    ref = _tx_ref(date_str, section, description, amount_str, currency)
    if ref in registered_txs:
        return None

    try:
        tx_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tzlocal())
    except ValueError, TypeError:
        return None

    tx_type = section_config["type_fn"](description, amount)

    return AccountTx(
        id=uuid4(),
        ref=ref,
        name=description,
        amount=round(abs(amount), 2),
        currency=currency,
        type=tx_type,
        date=tx_date,
        entity=IBKR,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        product_type=ProductType.ACCOUNT,
        source=DataSource.REAL,
    )
