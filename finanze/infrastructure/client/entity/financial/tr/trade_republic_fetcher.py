import logging
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.global_position import (
    Account,
    AccountType,
    GlobalPosition,
    Investments,
    StockDetail,
    StockInvestments,
)
from domain.native_entities import TRADE_REPUBLIC
from domain.fetch_result import FetchOptions
from domain.transactions import AccountTx, ProductType, StockTx, Transactions, TxType
from infrastructure.client.entity.financial.tr.trade_republic_client import (
    TradeRepublicClient,
)


def parse_sub_section_float(section: dict) -> Dezimal:
    if not section:
        return Dezimal(0)

    value = section["detail"]["text"]
    return parse_float(value)


def parse_float(value: str) -> Dezimal:
    value = value.replace("\xa0", "").strip()
    value = value.replace(",", "")
    numeric_value = re.sub(r"[^\d.]", "", value)
    return Dezimal(numeric_value)


def get_section(d, title):
    for section in d:
        if title.lower() in section.get("title", "").lower():
            return section
    return None


def map_investment_tx(raw_tx: dict, date: datetime) -> StockTx:
    name = raw_tx["title"].strip()
    amount_obj = raw_tx["amount"]
    currency = amount_obj["currency"]
    net_amount_val = round(Dezimal(amount_obj["value"]), 2)
    net_amount = abs(net_amount_val)

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

    return StockTx(
        id=uuid4(),
        ref=raw_tx["id"],
        name=name,
        amount=Dezimal(amount),
        currency=currency,
        type=tx_type,
        date=date,
        entity=TRADE_REPUBLIC,
        net_amount=Dezimal(net_amount),
        isin=isin,
        ticker=None,
        shares=Dezimal(shares),
        price=Dezimal(price),
        market=None,
        fees=Dezimal(fees + taxes),
        retentions=Dezimal(0),
        order_date=None,
        product_type=ProductType.STOCK_ETF,
        linked_tx=None,
        is_real=True,
    )


def map_account_tx(raw_tx: dict, date: datetime) -> AccountTx:
    title = raw_tx["title"].strip()
    subtitle = raw_tx["subtitle"].strip().replace("\xa0", "")
    name = f"{title} - {subtitle}"
    amount_obj = raw_tx["amount"]
    currency = amount_obj["currency"]

    detail_sections = raw_tx["details"]["sections"]

    ov_section = get_section(detail_sections, "Overview")["data"]
    avg_balance = parse_sub_section_float(get_section(ov_section, "Average balance"))
    annual_rate = parse_sub_section_float(get_section(ov_section, "Annual rate"))

    if not annual_rate:
        annual_rate = parse_float(subtitle.split(" ")[0])

    if raw_tx["eventType"] == "INTEREST_PAYOUT":
        tx_section = get_section(detail_sections, "Transaction")["data"]
        accrued = parse_sub_section_float(get_section(tx_section, "Accrued"))
        taxes = parse_sub_section_float(get_section(tx_section, "Tax"))
    else:
        taxes = 0
        accrued = amount_obj["value"]

    return AccountTx(
        id=uuid4(),
        ref=raw_tx["id"],
        name=name,
        amount=Dezimal(round(accrued, 2)),
        currency=currency,
        fees=Dezimal(0),
        retentions=Dezimal(round(taxes, 2)),
        interest_rate=Dezimal(round(annual_rate / 100, 4)),
        avg_balance=Dezimal(round(avg_balance, 2)),
        type=TxType.INTEREST,
        product_type=ProductType.ACCOUNT,
        date=date,
        entity=TRADE_REPUBLIC,
        is_real=True,
    )


DATE_FORMAT = "%Y-%m-%d"

CONTRIBUTION_FREQUENCY = {
    "weekly": ContributionFrequency.WEEKLY,
    "twoPerMonth": ContributionFrequency.BIWEEKLY,
    "monthly": ContributionFrequency.MONTHLY,
    "quarterly": ContributionFrequency.QUARTERLY,
}


class TradeRepublicFetcher(FinancialEntityFetcher):
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def __init__(self):
        self._client = TradeRepublicClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        two_factor = login_params.two_factor

        phone, pin = credentials["phone"], credentials["password"]
        process_id, code = None, None
        if two_factor:
            process_id, code = two_factor.process_id, two_factor.code
        return self._client.login(
            phone,
            pin,
            login_options=login_params.options,
            process_id=process_id,
            code=code,
            session=login_params.session,
        )

    async def _instrument_mapper(self, stock: dict, currency: str):
        isin = stock["instrumentId"]
        average_buy = round(Dezimal(stock["averageBuyIn"]), 4)
        shares = Dezimal(stock["netSize"])
        market_value = round(Dezimal(stock["netValue"]), 4)
        initial_investment = round(average_buy * shares, 4)

        details = await self._client.get_details(isin)
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
            # interest_rate = Dezimal(details.instrument["bondInfo"]["interestRate"])
            # maturity = datetime.strptime(details.instrument["bondInfo"]["maturityDate"], "%Y-%m-%d").date()

        if not subtype:
            subtype = type_id

        return StockDetail(
            id=uuid4(),
            name=name,
            ticker=ticker,
            isin=isin,
            market=", ".join(stock["exchangeIds"]),
            shares=shares,
            initial_investment=initial_investment,
            average_buy_price=average_buy,
            market_value=market_value,
            currency=currency,
            type=type_id,
            subtype=subtype,
        )

    async def global_position(self) -> GlobalPosition:
        user_info = self._client.get_user_info()
        cash_account = user_info.get("cashAccount")
        iban = None
        if cash_account:
            iban = cash_account.get("iban")

        active_interest = round(
            Dezimal(self._client.get_active_interest_rate().get("activeInterestRate"))
            / 100,
            4,
        )
        raw_portfolio = await self._client.get_portfolio()

        accounts = []
        currency = None
        for account in raw_portfolio.cash:
            currency = account["currencyId"]
            cash_total = Dezimal(account["amount"])
            accounts.append(
                Account(
                    id=uuid4(),
                    total=cash_total,
                    interest=active_interest,
                    currency=currency,
                    iban=iban,
                    type=AccountType.BROKERAGE,
                )
            )

        investments = []
        for position in raw_portfolio.portfolio["positions"]:
            investment = await self._instrument_mapper(position, currency)
            investments.append(investment)

        await self._client.close()

        initial_investment = round(
            sum(map(lambda x: x.initial_investment, investments)), 2
        )
        market_value = round(sum(map(lambda x: x.market_value, investments)), 4)

        investments_data = Investments(
            stocks=StockInvestments(
                investment=initial_investment,
                market_value=market_value,
                details=investments,
            )
        )

        return GlobalPosition(
            id=uuid4(),
            entity=TRADE_REPUBLIC,
            accounts=accounts,
            investments=investments_data,
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        raw_txs = await self._client.get_transactions(
            already_registered_ids=registered_txs, force_all=options.deep
        )
        await self._client.close()

        investment_txs = []
        account_txs = []
        for raw_tx in raw_txs:
            if raw_tx["id"] in registered_txs:
                continue

            status = raw_tx.get("status", None)
            event_type = raw_tx.get("eventType", None)
            if not (
                event_type
                and status == "EXECUTED"
                and event_type.upper()
                in [
                    "TRADE_INVOICE",
                    "ORDER_EXECUTED",
                    "INTEREST_PAYOUT",
                    "INTEREST_PAYOUT_CREATED",
                    "TRADING_TRADE_EXECUTED",
                ]
            ):
                continue

            date = datetime.strptime(raw_tx["timestamp"], self.DATETIME_FORMAT)

            if event_type in ["INTEREST_PAYOUT", "INTEREST_PAYOUT_CREATED"]:
                account_txs.append(map_account_tx(raw_tx, date))
            else:
                investment_txs.append(map_investment_tx(raw_tx, date))

        return Transactions(investment=investment_txs, account=account_txs)

    async def _map_saving_plan(
        self, saving_plan: dict, currency: str
    ) -> Optional[PeriodicContribution]:
        amount = round(Dezimal(saving_plan["amount"]), 2)
        isin = saving_plan["instrumentId"]

        frequency = CONTRIBUTION_FREQUENCY.get(saving_plan["interval"])
        if not frequency:
            self._log.warning(f"Unknown contribution frequency: {frequency}")
            return None

        active = not saving_plan["paused"]
        raw_start_date = saving_plan["startDate"]
        start_date_type = raw_start_date["type"]
        if start_date_type == "dayOfMonth":
            since_str = raw_start_date.get("nextExecutionDate")
            since = datetime.strptime(since_str, DATE_FORMAT).date()
            if not since:
                self._log.warning("No start date in saving plan")
                return None
        else:
            self._log.warning(f"Unknown start date type: {start_date_type}")
            return None

        isin_details = await self._client.get_instrument_details(isin)
        instrument_name = isin_details.get("shortName")

        return PeriodicContribution(
            id=uuid4(),
            alias=instrument_name,
            target=isin,
            target_type=ContributionTargetType.STOCK_ETF,
            amount=amount,
            currency=currency,
            since=since,
            until=None,
            frequency=frequency,
            active=active,
            is_real=True,
        )

    async def auto_contributions(self) -> AutoContributions:
        portfolio_details = await self._client.get_portfolio()
        saving_plans_response = await self._client.get_saving_plans()
        await self._client.close()

        user_currency = portfolio_details.cash[0]["currencyId"]

        saving_plans = saving_plans_response.get("savingsPlans")

        contributions = [
            await self._map_saving_plan(sp, user_currency) for sp in saving_plans if sp
        ]

        return AutoContributions(contributions)
