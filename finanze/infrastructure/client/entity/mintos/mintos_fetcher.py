from uuid import uuid4

from application.ports.entity_fetcher import EntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from domain.entity import EntitySetupLoginType
from domain.global_position import (
    Account,
    AccountType,
    Crowdlending,
    GlobalPosition,
    Investments,
)
from domain.native_entities import MINTOS
from infrastructure.client.entity.mintos.mintos_client import MintosAPIClient

CURRENCY_ID_MAPPING = {
    203: "CZK",
    978: "EUR",
    208: "DKK",
    826: "GBP",
    981: "GEL",
    398: "KZT",
    484: "MXN",
    985: "PLN",
    946: "RON",
    643: "RUB",
    752: "SEK",
    840: "USD",
}


def map_loan_distribution(input_json: dict) -> dict:
    mapping = {
        "active": {"count_key": "activeCount", "sum_key": "activeSum"},
        "gracePeriod": {
            "count_key": "delayedWithinGracePeriodCount",
            "sum_key": "delayedWithinGracePeriodSum",
        },
        "late1_15": {"count_key": "late115Count", "sum_key": "late115Sum"},
        "late16_30": {"count_key": "late1630Count", "sum_key": "late1630Sum"},
        "late31_60": {"count_key": "late3160Count", "sum_key": "late3160Sum"},
        "default": {"count_key": "defaultCount", "sum_key": "defaultSum"},
        "badDebt": {"count_key": "badDebtCount", "sum_key": "badDebtSum"},
        "recovery": {"count_key": "recoveryCount", "sum_key": "recoverySum"},
        "total": {"count_key": "totalCount", "sum_key": "totalSum"},
    }

    output_json = {}
    for key, value in mapping.items():
        count = input_json.get(value["count_key"], 0)
        sum_value = input_json.get(value["sum_key"], 0)

        output_json[key] = {"total": round(Dezimal(sum_value), 2), "count": count}

    return output_json


class MintosFetcher(EntityFetcher):
    def __init__(self):
        self._client = MintosAPIClient()
        if self._client.automated_login:
            MINTOS.setup_login_type = EntitySetupLoginType.AUTOMATED

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        if self._client.automated_login:
            return await self._client.login(username, password)

        elif "cookie" not in credentials and not self._client.has_completed_login():
            if login_params.options.avoid_new_login:
                return EntityLoginResult(code=LoginResultCode.NOT_LOGGED)

            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN, details=credentials
            )

        cookie_header = credentials.get("cookie")
        return self._client.complete_login(cookie_header)

    async def global_position(self) -> GlobalPosition:
        user_json = self._client.get_user()
        wallet = user_json["aggregates"][0]
        wallet_currency_id = wallet["currency"]
        currency_iso = CURRENCY_ID_MAPPING[wallet_currency_id]
        balance = wallet["accountBalance"]

        overview_json = self._client.get_overview(wallet_currency_id)
        loans = overview_json["loans"]["value"]

        overview_net_annual_returns_json = self._client.get_net_annual_returns(
            wallet_currency_id
        )
        net_annual_returns = overview_net_annual_returns_json["netAnnualReturns"][
            str(wallet_currency_id)
        ]

        portfolio_data_json = self._client.get_portfolio(wallet_currency_id)
        total_investment_distribution = portfolio_data_json[
            "totalInvestmentDistribution"
        ]

        account_data = Account(
            id=uuid4(),
            total=round(Dezimal(balance), 2),
            currency=currency_iso,
            type=AccountType.VIRTUAL_WALLET,
        )

        loan_distribution = map_loan_distribution(total_investment_distribution)

        return GlobalPosition(
            id=uuid4(),
            entity=MINTOS,
            accounts=[account_data],
            investments=Investments(
                crowdlending=Crowdlending(
                    id=uuid4(),
                    total=round(Dezimal(loans), 2),
                    weighted_interest_rate=round(Dezimal(net_annual_returns) / 100, 4),
                    currency=currency_iso,
                    distribution=loan_distribution,
                    details=[],
                )
            ),
        )
