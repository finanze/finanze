from datetime import datetime

from application.ports.entity_scraper import EntityScraper
from domain.global_position import Account, GlobalPosition, Investments, \
    Deposits, Deposit
from domain.scrap_result import LoginResult
from infrastructure.scrapers.f24.f24_client import F24APIClient

DATE_FORMAT = "%Y-%m-%d"


def _map_deposits(off_balance_entries: list):
    deposits = []
    for entry in off_balance_entries:
        if entry["type"] != "deposit":
            continue

        details = entry["details"]

        amount = float(entry["amount"])
        expected_profit = round(float(details["profitAll"]), 2)

        deposit = Deposit(
            name=details["name"],
            amount=round(float(amount - expected_profit), 2),
            totalInterests=expected_profit,
            interestRate=round(float(details["rate"]) / 100, 6),
            creation=datetime.strptime(details["startDate"], DATE_FORMAT),
            maturity=datetime.strptime(details["endDate"], DATE_FORMAT).date()
        )

        deposits.append(deposit)

    return deposits


def _get_balance(account: dict) -> float:
    return round(float(account["money_detailed"]["EUR"]["avail_money"]), 2)


class F24Scraper(EntityScraper):

    def __init__(self):
        self._client = F24APIClient()

    async def login(self, credentials: tuple, **kwargs) -> dict:
        username, password = credentials
        login_result = self._client.login(username, password)

        if login_result["result"] == LoginResult.CREATED:
            self._setup_users()

        return login_result

    async def global_position(self) -> GlobalPosition:
        savings_account_id = self._users["savings"]["id"]
        brokerage_account_id = self._users["brokerage"]["id"]

        savings_position = self._client.get_positions(savings_account_id)
        brokerage_position = self._client.get_positions(brokerage_account_id)

        savings_balance = _get_balance(savings_position)
        brokerage_balance = _get_balance(brokerage_position)

        account_data = Account(
            total=savings_balance + brokerage_balance,
            retained=None,
            interest=0
        )

        deposits = None
        if brokerage_position["offbalance"]:
            off_balance_entries = self._client.get_off_balance()

            deposit_details = _map_deposits(off_balance_entries["accounts"])

            total_invested = round(sum([inv.amount for inv in deposit_details]), 2)
            total_interests = round(sum([inv.totalInterests for inv in deposit_details]), 2)
            weighted_interest_rate = round(
                (sum([inv.amount * inv.interestRate for inv in deposit_details])
                 / sum([inv.amount for inv in deposit_details])),
                6,
            )

            deposits = Deposits(
                total=total_invested,
                totalInterests=total_interests,
                weightedInterestRate=weighted_interest_rate,
                details=deposit_details
            )

        return GlobalPosition(
            account=account_data,
            investments=Investments(
                deposits=deposits,
            )
        )

    def _get_positions(self, user_id: str) -> dict:
        return self._client.get_positions(user_id)

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
