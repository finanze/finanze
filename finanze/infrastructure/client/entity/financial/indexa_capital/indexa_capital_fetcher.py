import logging
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.global_position import (
    Account,
    AccountType,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    GlobalPosition,
    Investments,
)
from domain.native_entities import INDEXA_CAPITAL
from infrastructure.client.entity.financial.indexa_capital.indexa_capital_client import (
    IndexaCapitalClient,
)


class IndexaCapitalFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = IndexaCapitalClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        token = login_params.credentials.get("token")
        return self._client.setup(token)

    async def global_position(self) -> GlobalPosition:
        user_info = self._client.get_user_info()
        accounts_list = []
        fund_details = []
        fund_portfolios = []
        total_initial_investment = Dezimal(0)
        total_market_value = Dezimal(0)
        asset_cash = Dezimal(0)

        for account_data in user_info["accounts"]:
            account_number = account_data.get("account_number")
            account_name = account_number
            iban = account_data.get("account_cash")
            account_currency = account_data.get("currency")

            portfolio_data = self._client.get_portfolio(account_number)
            portfolio_info = portfolio_data.get("portfolio", {})

            cash_amount = portfolio_info.get("cash_amount", 0)
            total_cash = Dezimal(cash_amount)

            fund_portfolio_id = uuid4()

            instrument_accounts = portfolio_info.get("instrument_accounts", [])
            for account_item in instrument_accounts:
                positions = account_item.get("positions", [])
                for pos in positions:
                    market_value = Dezimal(pos.get("amount", 0))

                    instrument = pos.get("instrument", {})
                    asset_type = instrument.get("asset_class")
                    if asset_type != "cash_euro":  # equity, fixed
                        asset_cash += market_value
                        continue

                    titles = Dezimal(pos.get("titles", 0))
                    initial_investment = Dezimal(pos.get("cost_amount", 0))

                    if market_value == 0 or initial_investment == 0 or titles == 0:
                        continue

                    price = Dezimal(pos.get("price", 0))

                    total_initial_investment += initial_investment
                    total_market_value += market_value

                    fund_details.append(
                        FundDetail(
                            id=uuid4(),
                            name=instrument.get("name"),
                            isin=instrument["identifier"],
                            market=instrument.get("market_code"),
                            shares=titles,
                            initial_investment=initial_investment,
                            average_buy_price=price,
                            market_value=market_value,
                            currency=account_currency,
                            portfolio=FundPortfolio(id=fund_portfolio_id),
                        )
                    )

            fund_portfolios.append(
                FundPortfolio(
                    id=fund_portfolio_id,
                    name=account_name,
                    currency=account_currency,
                    initial_investment=total_cash,
                    market_value=total_cash,
                )
            )

            account = Account(
                id=uuid4(),
                name=account_name,
                iban=iban,
                total=total_cash,
                currency=account_currency,
                retained=asset_cash,
                type=AccountType.FUND_PORTFOLIO,
            )
            accounts_list.append(account)

        funds = FundInvestments(
            investment=total_initial_investment,
            market_value=total_market_value,
            details=fund_details,
        )
        investments = Investments(funds=funds, fund_portfolios=fund_portfolios)

        return GlobalPosition(
            id=uuid4(),
            entity=INDEXA_CAPITAL,
            accounts=accounts_list,
            investments=investments,
        )
