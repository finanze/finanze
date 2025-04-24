import re
from datetime import datetime
from uuid import uuid4

from application.ports.entity_scraper import EntityScraper
from domain.dezimal import Dezimal
from domain.global_position import Account, GlobalPosition, Investments, \
    Deposits, Deposit, AccountType
from domain.login import LoginResultCode, LoginParams, LoginResult
from domain.native_entities import F24
from domain.transactions import Transactions, AccountTx, TxType
from infrastructure.scrapers.f24.f24_client import F24APIClient

DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

DATE_FORMAT = "%Y-%m-%d"

INTEREST_YEARLY_PAYMENTS = 365


def _map_deposits(off_balance_entries: list):
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
            maturity=datetime.strptime(details["endDate"], DATE_FORMAT).date()
        )

        deposits.append(deposit)

    return deposits


def _get_balance(account: dict, default_currency: str) -> tuple[Dezimal | None, str | None]:
    money_entries = account["money_detailed"]
    highest_amount = Dezimal(0)
    highest_currency = default_currency
    for currency, details in money_entries.items():
        amount = Dezimal(details["Smoney"])
        if amount > highest_amount:
            highest_amount = amount
            highest_currency = currency

    return round(Dezimal(money_entries[highest_currency]["avail_money"]), 2), highest_currency


def _parse_interests_from_desc(text: str) -> dict[str, Dezimal]:
    pattern = r'(\d+(?:\.\d+)?)%\s*([A-Z]{3})'
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

        trade_date = datetime.strptime(trade["date"], DATE_TIME_FORMAT)
        avg_balance = round(Dezimal(trade["sum"]), 2)
        interest_rate = Dezimal(0)
        if avg_balance > Dezimal(0):
            interest_rate = round(profit * INTEREST_YEARLY_PAYMENTS / avg_balance, 4)

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
            date=trade_date,
            entity=F24,
            is_real=True
        )
        account_txs.append(account_tx)
    return account_txs


class F24Scraper(EntityScraper):

    def __init__(self):
        self._client = F24APIClient()

    async def login(self, login_params: LoginParams) -> LoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        login_result = self._client.login(username, password)

        if login_result.code == LoginResultCode.CREATED:
            self._setup_users()

        return login_result

    async def global_position(self) -> GlobalPosition:
        savings_account_id = self._users["savings"]["id"]
        brokerage_account_id = self._users["brokerage"]["id"]

        savings_position = self._client.get_positions(savings_account_id)
        brokerage_position = self._client.get_positions(brokerage_account_id)

        savings_balance, savings_currency = _get_balance(savings_position, "EUR")
        brokerage_balance, brokerage_currency = _get_balance(brokerage_position, savings_currency)

        accounts = []
        if savings_currency:
            user_assets = self._client.get_connected_users_assets()
            savings_account = None
            if user_assets.get("users"):
                savings_account = next((acc for acc in user_assets["users"] if acc["account_type"] == "savings"), None)

            d_account_description = savings_account.get("account_type_description")
            savings_interests = _parse_interests_from_desc(d_account_description)

            savings_currency_interests = Dezimal(0)
            if savings_currency in savings_interests:
                savings_currency_interests = round(savings_interests.get(savings_currency) / 100, 4)

            accounts.append(Account(
                id=uuid4(),
                type=AccountType.SAVINGS,
                total=savings_balance,
                currency=savings_currency,
                retained=None,
                interest=savings_currency_interests
            ))

        if brokerage_currency:
            accounts.append(Account(
                id=uuid4(),
                type=AccountType.BROKERAGE,
                total=brokerage_balance,
                currency=brokerage_currency,
                retained=None,
                interest=Dezimal(0)
            ))

        deposits = None
        if brokerage_position["offbalance"]:
            off_balance_entries = self._client.get_off_balance()

            deposit_details = _map_deposits(off_balance_entries["accounts"])

            total_invested = round(sum([inv.amount for inv in deposit_details]), 2)
            total_interests = round(sum([inv.expected_interests for inv in deposit_details]), 2)
            weighted_interest_rate = round(
                (sum([inv.amount * inv.interest_rate for inv in deposit_details])
                 / sum([inv.amount for inv in deposit_details])),
                6,
            )

            deposits = Deposits(
                total=total_invested,
                expected_interests=total_interests,
                weighted_interest_rate=weighted_interest_rate,
                details=deposit_details
            )

        return GlobalPosition(
            id=uuid4(),
            entity=F24,
            accounts=accounts,
            investments=Investments(
                deposits=deposits,
            )
        )

    def _get_positions(self, user_id: str) -> dict:
        return self._client.get_positions(user_id)

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        savings_account_id = self._users["savings"]["id"]
        tr_systems_id = self._users["savings"]["trader_systems_id"]
        self._client.switch_user(tr_systems_id)
        raw_trades = self._client.get_trades(savings_account_id).get("trades", [])

        account_txs = _map_account_txs(raw_trades, registered_txs)

        return Transactions(investment=[], account=account_txs)

    def _setup_users(self):
        user_info_raw = self._client.get_user_info()

        users = {}

        accounts = user_info_raw["accounts"]
        for acc in accounts:
            acc_type = acc["account_type"]
            if acc_type in ["brokerage", "savings"]:
                users[acc_type] = {}
                users[acc_type]["id"] = str(acc["user_id"])
                users[acc_type]["trader_systems_id"] = acc["trader_systems_id"]

        self._users = users
