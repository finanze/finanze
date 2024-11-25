import re
from datetime import datetime
from typing import Optional

from dateutil.tz import tzlocal

from application.ports.bank_scraper import BankScraper
from domain.bank import Bank
from domain.bank_data import StockDetail, Investments, Account, BankGlobalPosition, StockInvestments
from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.transactions import Transactions, StockTx, TxProductType, TxType
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
            name = details.stock_details["company"]["name"]
            ticker = details.stock_details["company"]["tickerSymbol"]

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
            date=datetime.now(tzlocal()),
            account=Account(
                total=cash_total,
            ),
            investments=investments_data,
        )

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        def get_section(d, title):
            for section in d:
                if title.lower() in section.get("title", "").lower():
                    return section
            return None

        def parse_sub_section_float(section: dict):
            if not section:
                return 0.0

            value = section["detail"]["text"]
            value = value.replace("\xa0", "").strip()
            value = value.replace(",", "")
            numeric_value = re.sub(r"[^\d.]", "", value)
            return float(numeric_value)

        raw_txs = await self.__client.get_transactions(already_registered_ids=registered_txs)

        investment_txs = []
        for raw_tx in raw_txs:
            status = raw_tx.get("status", None)
            event_type = raw_tx.get("eventType", None)
            if not (status == "EXECUTED" and event_type in ["TRADE_INVOICE", "ORDER_EXECUTED"]):
                continue

            date = datetime.fromisoformat(raw_tx["timestamp"][:19])
            name = raw_tx["title"].strip()
            amount_obj = raw_tx["amount"]
            net_amount_val = round(amount_obj["value"], 2)
            net_amount = abs(net_amount_val)
            currency = amount_obj["currency"]
            tx_type = TxType.SELL if net_amount_val > 0 else TxType.BUY

            detail_sections = raw_tx["details"]["sections"]

            isin = detail_sections[0]["action"]["payload"]
            tx_section = get_section(detail_sections, "Transaction")["data"]
            shares = parse_sub_section_float(get_section(tx_section, "Shares"))
            taxes = parse_sub_section_float(get_section(tx_section, "Tax"))
            fees = parse_sub_section_float(get_section(tx_section, "Fee"))

            amount = abs(net_amount_val + fees + taxes)
            # Provided price sometimes doesn't match with the executed price
            price = round(amount / shares, 4)

            investment_tx = StockTx(
                id=raw_tx["id"],
                name=name,
                amount=amount,
                currency=currency,
                currencySymbol=CURRENCY_SYMBOL_MAP.get(currency, currency),
                type=tx_type,
                date=date,
                source=Bank.TRADE_REPUBLIC,
                netAmount=net_amount,
                isin=isin,
                ticker=None,
                shares=shares,
                price=price,
                market=None,
                fees=fees + taxes,
                orderDate=None,
                productType=TxProductType.STOCK_ETF,
            )
            investment_txs.append(investment_tx)

        return Transactions(investment=investment_txs)
