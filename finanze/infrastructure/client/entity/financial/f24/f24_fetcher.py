import calendar
import json
import logging
import re
from datetime import date, datetime
from hashlib import sha1
from typing import Optional
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Deposit,
    Deposits,
    EquityType,
    GlobalPosition,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.native_entities import F24
from domain.transactions import (
    AccountTx,
    DepositTx,
    StockTx,
    Transactions,
    TxType,
)
from infrastructure.client.entity.financial.f24.f24_client import F24APIClient

DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

DATE_FORMAT = "%Y-%m-%d"

_FX_IN_COMMENT = re.compile(
    r"Currency exchange of trade \(([A-Z]{3})\) to a currency exchange of the service plan \(([A-Z]{3})\) is ([0-9]+(?:\.[0-9]+)?)"
)
_CCY_PAIR_TICKER = re.compile(r"^[A-Z]{3}/[A-Z]{3}(?:\.[A-Z]+)?$")

_log = logging.getLogger(__name__)


def _map_deposits(off_balance_entries: list) -> list[Deposit]:
    deposits = []
    for entry in off_balance_entries:
        if entry["type"] != "deposit":
            continue

        details = entry["details"]

        amount = Dezimal(entry["amount"])
        expected_profit = round(Dezimal(details["profitAll"]), 2)

        deposit = Deposit(
            id=uuid4(),
            name=details["name"],
            amount=round(amount - expected_profit, 2),
            currency=entry["currency"],
            expected_interests=expected_profit,
            interest_rate=round(Dezimal(details["rate"]) / 100, 6),
            creation=datetime.strptime(details["startDate"], DATE_FORMAT),
            maturity=datetime.strptime(details["endDate"], DATE_FORMAT).date(),
        )

        deposits.append(deposit)

    return deposits


def _get_balance(
    account: dict, default_currency: str
) -> tuple[Dezimal | None, str | None]:
    money_entries = account["money_detailed"]
    highest_amount = Dezimal(0)
    highest_currency = default_currency
    for currency, details in money_entries.items():
        amount = Dezimal(details["Smoney"])
        if amount > highest_amount:
            highest_amount = amount
            highest_currency = currency

    return round(
        Dezimal(money_entries[highest_currency]["avail_money"]), 2
    ), highest_currency


def _map_brokerage_cash(position: dict) -> list[Account]:
    money_entries = (position or {}).get("money_detailed") or {}
    accounts = []
    for currency, details in money_entries.items():
        amount = round(Dezimal(details.get("Smoney") or 0), 2)
        if amount == Dezimal(0):
            continue
        accounts.append(
            Account(
                id=uuid4(),
                type=AccountType.BROKERAGE,
                total=amount,
                currency=currency,
                retained=None,
                interest=Dezimal(0),
            )
        )
    return accounts


def _position_market_value(pos: dict, shares: Dezimal) -> Dezimal:
    market_value = Dezimal(pos.get("market_value") or 0)
    mkt_price = Dezimal(pos.get("mkt_price") or 0)
    if shares > Dezimal(1) and mkt_price > Dezimal(0):
        per_share_gap = abs(market_value - mkt_price)
        notional_gap = abs(market_value - shares * mkt_price)
        if per_share_gap < notional_gap:
            return market_value * shares
    return market_value


def _position_average_buy_price(pos: dict) -> Dezimal:
    raw = pos.get("price_a")
    if raw is None:
        raw = pos.get("bal_price_a")
    return Dezimal(0 if raw is None else raw)


F24_KIND_STOCK = 1
F24_KIND_ETF = 7


def _parse_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _equity_type(kind) -> EquityType | None:
    parsed = _parse_int(kind)
    if parsed == F24_KIND_ETF:
        return EquityType.ETF
    if parsed == F24_KIND_STOCK:
        return EquityType.STOCK
    return None


def _trade_fee(trade: dict) -> Dezimal:
    fee = Dezimal(trade.get("commission") or 0)
    if fee == Dezimal(0):
        return Dezimal(0)

    trade_ccy = trade.get("currency")
    fee_ccy = trade.get("commission_currency") or trade_ccy
    if not fee_ccy or fee_ccy == trade_ccy:
        return round(fee, 2)

    comment = trade.get("commission_comment") or ""
    match = _FX_IN_COMMENT.search(comment)
    if not match:
        _log.warning(
            "F24 trade %s: commission %s %s vs trade %s, no FX rate in comment",
            trade.get("ticker"),
            fee,
            fee_ccy,
            trade_ccy,
        )
        return round(fee, 2)

    from_ccy, to_ccy, rate = match.group(1), match.group(2), Dezimal(match.group(3))
    if rate <= Dezimal(0):
        _log.warning(
            "F24 trade %s: invalid FX rate %s in comment",
            trade.get("ticker"),
            rate,
        )
        return round(fee, 2)

    if from_ccy == trade_ccy and to_ccy == fee_ccy:
        return round(fee / rate, 2)
    if from_ccy == fee_ccy and to_ccy == trade_ccy:
        return round(fee * rate, 2)

    _log.warning(
        "F24 trade %s: FX comment %s->%s does not match commission %s vs trade %s",
        trade.get("ticker"),
        from_ccy,
        to_ccy,
        fee_ccy,
        trade_ccy,
    )
    return round(fee, 2)


def _currency_pair_tickers(raw) -> set[str]:
    payload = raw
    if isinstance(raw, dict):
        tickers = raw.get("tickers")
        if tickers is None:
            for key in ("result", "data", "response"):
                nested = raw.get(key)
                if isinstance(nested, dict) and nested.get("tickers") is not None:
                    payload = nested
                    tickers = nested.get("tickers")
                    break
        else:
            payload = raw
    else:
        tickers = None

    pairs: set[str] = set()
    if isinstance(tickers, dict):
        for key, value in tickers.items():
            if key:
                pairs.add(str(key).strip())
            if value:
                pairs.add(str(value).strip())
    elif isinstance(tickers, list):
        for value in tickers:
            if value:
                pairs.add(str(value).strip())

    if isinstance(payload, dict):
        for fiat in payload.get("fiat") or []:
            code = str(fiat).strip()
            if code:
                pairs.add(code)
    return pairs


def _is_currency_pair(ticker: str, pairs: set[str]) -> bool:
    ticker = (ticker or "").strip()
    if not ticker:
        return False
    if ticker in pairs:
        return True
    return bool(_CCY_PAIR_TICKER.fullmatch(ticker))


def _as_ticker_info(ticker_info) -> dict:
    if isinstance(ticker_info, list):
        first = ticker_info[0] if ticker_info else None
        return first if isinstance(first, dict) else {}
    if not isinstance(ticker_info, dict):
        return {}
    if any(key in ticker_info for key in ("kind", "k", "isin", "nm", "mkt")):
        return ticker_info
    for value in ticker_info.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
    return ticker_info


def _map_stocks(raw_positions: list | None) -> list[StockDetail]:
    stocks = []
    for pos in raw_positions or []:
        ticker = pos.get("i") or pos.get("base_contract_code") or ""
        name = pos.get("name") or pos.get("name2") or ticker or pos.get("instr_id")

        if pos.get("t") not in (None, 1):
            _log.warning(
                "Skipping F24 position %s: unsupported type t=%s",
                name,
                pos.get("t"),
            )
            continue

        equity_type = _equity_type(pos.get("k", pos.get("kind")))
        if equity_type is None:
            _log.warning(
                "Skipping F24 position %s: unsupported kind k=%s",
                name,
                pos.get("k", pos.get("kind")),
            )
            continue

        shares = Dezimal(pos.get("q") or 0)
        if shares <= Dezimal(0):
            _log.warning(
                "Skipping F24 position %s: non-positive shares q=%s",
                name,
                pos.get("q"),
            )
            continue

        currency = pos.get("curr") or pos.get("base_currency")
        if not ticker or not currency:
            _log.warning(
                "Skipping F24 position %s: missing ticker or currency ticker=%s currency=%s",
                name,
                ticker,
                currency,
            )
            continue

        market_value = round(_position_market_value(pos, shares), 2)
        market = ticker.rsplit(".", 1)[-1] if "." in ticker else ""
        average_buy_price = _position_average_buy_price(pos)

        stocks.append(
            StockDetail(
                id=uuid4(),
                name=pos.get("name") or pos.get("name2") or ticker,
                ticker=ticker,
                isin=pos.get("issue_nb") or ticker,
                shares=shares,
                market_value=market_value,
                currency=currency,
                type=equity_type,
                initial_investment=round(average_buy_price * shares, 2),
                average_buy_price=average_buy_price,
                market=market,
                source=DataSource.REAL,
            )
        )
    return stocks


def _parse_interests_from_desc(text: str) -> dict[str, Dezimal]:
    pattern = r"(\d+(?:\.\d+)?)%\s*([A-Z]{3})"
    found = re.findall(pattern, text)
    return {currency: Dezimal(amount) for amount, currency in found}


def _map_account_txs(raw_trades, registered_txs):
    account_txs = []
    for trade in raw_trades:
        trade_id = str(trade["trade_id"])
        if trade_id in registered_txs:
            continue

        profit = round(Dezimal(trade["profit"]), 2)
        if profit <= Dezimal(0):
            continue

        trade_date = datetime.strptime(trade["date"], DATE_TIME_FORMAT).astimezone(
            tzlocal()
        )
        avg_balance = round(Dezimal(trade["sum"]), 2)
        interest_rate = Dezimal(0)
        if avg_balance > Dezimal(0):
            pay_d = datetime.strptime(trade.get("pay_d", None), DATE_FORMAT).astimezone(
                tzlocal()
            )
            payment_days = (pay_d - trade_date).days + 1
            year_days = 365 + calendar.isleap(datetime.now().year)
            interest_rate = round(
                profit * Dezimal(year_days / payment_days) / avg_balance, 4
            )

        operation_desc = trade.get("operation").strip()
        pay_d = trade.get("pay_d", trade_date.strftime(DATE_FORMAT))
        name = f"{pay_d} - {operation_desc}"

        account_tx = AccountTx(
            id=uuid4(),
            ref=trade_id,
            name=name,
            amount=profit,
            currency=trade["currency"],
            fees=trade.get("commission", Dezimal(0)),
            retentions=Dezimal(0),
            interest_rate=interest_rate,
            avg_balance=avg_balance,
            type=TxType.INTEREST,
            product_type=ProductType.ACCOUNT,
            date=trade_date,
            entity=F24,
            source=DataSource.REAL,
        )
        account_txs.append(account_tx)
    return account_txs


def _get_ref(tx_id: str, tx_type: TxType) -> str:
    return sha1(f"{tx_id}-{tx_type}".encode("UTF-8")).hexdigest()


def _map_deposit_tx(
    tx_id, tx_type, name, amount, tx_date, currency, registered_txs
) -> Optional[DepositTx]:
    ref = _get_ref(tx_id, tx_type)
    if ref in registered_txs:
        return None

    return DepositTx(
        id=uuid4(),
        ref=ref,
        name=name,
        amount=amount,
        currency=currency,
        type=tx_type,
        date=tx_date,
        entity=F24,
        product_type=ProductType.DEPOSIT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=amount,
        source=DataSource.REAL,
    )


class F24Fetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = F24APIClient()

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        login_result = await self._client.login(username, password)

        if login_result.code == LoginResultCode.CREATED:
            await self._setup_users()

        return login_result

    async def global_position(self) -> GlobalPosition:
        savings_position = None
        savings_entry = self._users.get("savings", {})
        if savings_entry:
            savings_account_id = savings_entry.get("id")
            savings_position = await self._client.get_positions(savings_account_id)

        brokerage_position = None
        brokerage_entry = self._users.get("brokerage", {})
        if brokerage_entry:
            brokerage_account_id = brokerage_entry.get("id")
            brokerage_position = await self._client.get_positions(brokerage_account_id)

        savings_currency = "EUR"
        savings_balance = None
        if savings_position:
            savings_balance, savings_currency = _get_balance(savings_position, "EUR")

        accounts = []
        if savings_currency and savings_position:
            users = await self._client.get_connected_users_assets()
            savings_account = None
            if users.get("users"):
                savings_account = next(
                    (acc for acc in users["users"] if acc["account_type"] == "savings"),
                    None,
                )

            d_account_description = savings_account.get("account_type_description")
            if d_account_description:
                savings_interests = _parse_interests_from_desc(d_account_description)

                savings_currency_interests = Dezimal(0)
                if savings_currency in savings_interests:
                    savings_currency_interests = round(
                        savings_interests.get(savings_currency) / 100, 4
                    )

                accounts.append(
                    Account(
                        id=uuid4(),
                        type=AccountType.SAVINGS,
                        total=savings_balance,
                        currency=savings_currency,
                        retained=None,
                        interest=savings_currency_interests,
                    )
                )

        if brokerage_position:
            accounts.extend(_map_brokerage_cash(brokerage_position))

        products = {ProductType.ACCOUNT: Accounts(accounts)}

        if brokerage_position:
            stocks = _map_stocks(brokerage_position.get("pos"))
            if stocks:
                products[ProductType.STOCK_ETF] = StockInvestments(stocks)

        if brokerage_position and brokerage_position["offbalance"]:
            off_balance_entries = await self._client.get_off_balance()

            deposit_details = _map_deposits(off_balance_entries["accounts"])

            if deposit_details:
                deposits = Deposits(deposit_details)
                products[ProductType.DEPOSIT] = deposits

        return GlobalPosition(id=uuid4(), entity=F24, products=products)

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        account_txs = []
        savings_entry = self._users.get("savings", {})
        if savings_entry:
            savings_account_id = savings_entry.get("id")
            tr_systems_id = savings_entry.get("trader_systems_id")
            await self._client.switch_user(tr_systems_id)

            raw_trades = (await self._client.get_trades(savings_account_id)).get(
                "trades", []
            )
            account_txs = _map_account_txs(raw_trades, registered_txs)

        brokerage_entry = self._users.get("brokerage", {})
        investment_txs = []
        if brokerage_entry:
            brokerage_account_id = brokerage_entry.get("id")
            b_systems_id = brokerage_entry.get("trader_systems_id")
            await self._client.switch_user(b_systems_id)

            raw_trades = (await self._client.get_trades(brokerage_account_id)).get(
                "trades", []
            )
            investment_txs = await self._map_investment_txs(raw_trades, registered_txs)

            deposit_txs = await self._get_deposit_interest_txs(registered_txs)
            investment_txs = investment_txs + deposit_txs

        return Transactions(investment=investment_txs, account=account_txs)

    async def _get_deposit_interest_txs(self, registered_txs) -> list[DepositTx]:
        raw_order_history = await self._client.get_orders_history(
            from_date=date.fromisocalendar(2000, 1, 1)
        )
        txs = []
        raw_txs = raw_order_history.get("orders", {})
        raw_txs = raw_txs.get("order", [])
        for order in raw_txs:
            tx_id = str(order["id"])

            if order["instr"] != "FRHC.US":
                continue

            trades = order["trade"]
            matching_trade = next(
                (trade for trade in trades if trade["profit"] > 0), None
            )
            if not matching_trade:
                continue

            raw_trade_details = matching_trade["details"]
            trade_details = json.loads(raw_trade_details.replace("\\", ""))
            is_deposit = trade_details.get("is_long_term_deposit")
            currency = trade_details.get("commission_currency")
            if not is_deposit or not currency:
                continue

            pay_date = order.get("EndDate")
            if not pay_date:
                continue

            placed_amount = Dezimal(order["StartCash"])
            placement_date = datetime.fromisoformat(order["stat_d"]).replace(
                tzinfo=tzlocal()
            )
            name = order["order_nb"]
            pay_date = datetime.strptime(pay_date[:10], DATE_FORMAT).date()

            tx_type = TxType.INVESTMENT
            tx = _map_deposit_tx(
                tx_id,
                tx_type,
                name,
                placed_amount,
                placement_date,
                currency,
                registered_txs,
            )
            if tx:
                txs.append(tx)

            if pay_date >= datetime.now().date():  # Matured
                continue

            tx_type = TxType.REPAYMENT
            tx = _map_deposit_tx(
                tx_id,
                tx_type,
                name,
                placed_amount,
                pay_date,
                currency,
                registered_txs,
            )
            if tx:
                txs.append(tx)

            tx_type = TxType.INTEREST
            gross_return = Dezimal(order["EndCash"])
            interest = gross_return - placed_amount
            tx = _map_deposit_tx(
                tx_id,
                tx_type,
                name,
                interest,
                pay_date,
                currency,
                registered_txs,
            )
            if tx:
                txs.append(tx)

        return txs

    async def _map_investment_txs(self, raw_trades, registered_txs):
        currency_pairs = _currency_pair_tickers(
            await self._client.get_allowed_currency_pairs()
        )
        investment_tx = []
        for trade in raw_trades:
            trade_id = str(trade["trade_id"])
            if trade_id in registered_txs:
                continue

            ticker = (trade.get("ticker") or "").strip()
            if _is_currency_pair(ticker, currency_pairs):
                continue

            trade_date = datetime.strptime(trade["date"], DATE_TIME_FORMAT).astimezone(
                tzlocal()
            )

            operation = trade.get("operation").strip()
            if operation == "Sell":
                tx_type = TxType.SELL
            elif operation == "Buy":
                tx_type = TxType.BUY
            else:
                continue

            amount = round(Dezimal(trade["sum"]), 2)
            shares = Dezimal(trade["q"])
            price = Dezimal(trade["p"])
            fee = _trade_fee(trade)

            ticker_info = _as_ticker_info(await self._client.find_by_ticker(ticker))
            instrument_type = _parse_int(ticker_info.get("type", ticker_info.get("t")))
            equity_type = _equity_type(ticker_info.get("kind", ticker_info.get("k")))
            if instrument_type not in (None, 1) or equity_type is None:
                _log.warning(
                    "Skipping F24 trade %s: unsupported type t=%s kind k=%s",
                    ticker,
                    instrument_type,
                    ticker_info.get("kind", ticker_info.get("k")),
                )
                continue

            isin = ticker_info.get("isin")
            market = ticker_info.get("mkt")
            name = ticker_info.get("nm", ticker)

            tx = StockTx(
                id=uuid4(),
                ref=trade_id,
                name=name,
                amount=amount + fee,
                currency=trade["currency"],
                type=tx_type,
                date=trade_date,
                entity=F24,
                net_amount=amount,
                isin=isin,
                ticker=ticker,
                shares=Dezimal(shares),
                price=Dezimal(price),
                market=market,
                fees=fee,
                retentions=Dezimal(0),
                order_date=None,
                product_type=ProductType.STOCK_ETF,
                equity_type=equity_type,
                linked_tx=None,
                source=DataSource.REAL,
            )
            investment_tx.append(tx)

        return investment_tx

    async def _setup_users(self):
        user_info_raw = await self._client.get_connected_users_assets()

        users = {}

        accounts = user_info_raw.get("users", [])
        for acc in accounts:
            acc_type = acc.get("account_type")
            if acc_type in ["brokerage", "savings"]:
                users[acc_type] = {}
                users[acc_type]["id"] = str(acc["id"])
                users[acc_type]["trader_systems_id"] = acc["trader_systems_id"]

        self._users = users
