from datetime import datetime, timezone
from typing import Optional

from application.ports.bank_scraper import BankScraper
from domain.bank_data import StockDetail, Investments, Account, BankGlobalPosition, StockInvestments
from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from infrastructure.scrapers.trade_republic_client import TradeRepublicClient


class TradeRepublicSummaryGenerator(BankScraper):

    def __init__(self):
        self.__client = TradeRepublicClient()

    def login(self, credentials: tuple, **kwargs) -> Optional[dict]:
        phone, pin = credentials
        process_id = kwargs.get("processId", None)
        code = kwargs.get("code", None)
        return self.__client.login(phone, pin, process_id, code)

    async def instrument_mapper(self, stock: dict, currency: str):
        isin = stock["instrumentId"]
        average_buy = round(float(stock["averageBuyIn"]), 4)
        shares = float(stock["netSize"])
        market_value = round(float(stock["netValue"]), 4)
        initial_investment = round(average_buy * shares, 4)

        details = await self.__client.get_details(isin)
        type_id = details.instrument["typeId"].upper()
        name = details.instrument["name"]
        ticker = details.instrument["homeSymbol"]
        subtype = ""

        if type_id == "FUND":
            type_id = "ETF"

        elif type_id == "STOCK":
            name = details.stockDetails["company"]["name"]
            ticker = details.stockDetails["company"]["tickerSymbol"]

        elif type_id == "BOND":
            name = ""
            subtype = details.instrument["bondInfo"]["issuerClassification"]
            interest_rate = details.instrument["bondInfo"]["interestRate"]
            maturity = datetime.strptime(details.instrument["bondInfo"]["maturityDate"], "%Y-%m-%d").date()

        if not subtype:
            subtype = type_id

        return StockDetail(
            name=name,
            ticker=ticker,
            isin=isin,
            market=", ".join(stock["exchangeIds"]),
            shares=shares,
            initialInvestment=initial_investment,
            averageBuyPrice=average_buy,
            marketValue=market_value,
            currency=currency,
            currencySymbol=CURRENCY_SYMBOL_MAP.get(currency, currency),
            type=type_id,
            subtype=subtype
        )

    async def global_position(self) -> BankGlobalPosition:
        portfolio = await self.__client.get_portfolio()

        currency = portfolio.cash[0]["currencyId"]
        cash_total = portfolio.cash[0]["amount"]

        investments = []
        for position in portfolio.portfolio["positions"]:
            investment = await self.instrument_mapper(position, currency)
            investments.append(investment)

        initial_investment = round(
            sum(map(lambda x: x.initialInvestment, investments)), 4
        )
        market_value = round(sum(map(lambda x: x.marketValue, investments)), 4)

        investments_data = Investments(
            stocks=StockInvestments(
                initialInvestment=initial_investment,
                marketValue=market_value,
                details=investments,
            )
        )

        return BankGlobalPosition(
            date=datetime.now(timezone.utc),
            account=Account(
                total=cash_total,
            ),
            investments=investments_data,
        )
