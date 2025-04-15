import logging
import traceback
from datetime import date, datetime
from uuid import uuid4

from application.ports.entity_scraper import EntityScraper
from domain.auto_contributions import PeriodicContribution, ContributionFrequency, AutoContributions
from domain.currency_symbols import SYMBOL_CURRENCY_MAP
from domain.dezimal import Dezimal
from domain.global_position import Account, Card, StockDetail, StockInvestments, \
    FundDetail, \
    FundInvestments, Investments, GlobalPosition, \
    Deposit, Deposits, AccountType, CardType
from domain.login_result import LoginParams
from domain.native_entities import MY_INVESTOR
from domain.transactions import Transactions, FundTx, TxType, StockTx, ProductType
from infrastructure.scrapers.myinvestor.v2.myinvestor_client import MyInvestorAPIV2Client

DATE_FORMAT = "%Y-%m-%d"
ISO_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class MyInvestorScraperV2(EntityScraper):

    def __init__(self):
        self._client = MyInvestorAPIV2Client()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: LoginParams) -> dict:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        return self._client.login(username, password)

    async def global_position(self) -> GlobalPosition:
        # maintenance = self._client.check_maintenance()

        account_id, securities_account_id, account_data = self.scrape_account()

        cards_data = self.scrape_cards(account_id, account_data)

        investments_data = self.scrape_investments(securities_account_id)

        return GlobalPosition(
            id=uuid4(),
            entity=MY_INVESTOR,
            accounts=[account_data],
            cards=cards_data,
            investments=investments_data,
        )

    async def auto_contributions(self) -> AutoContributions:
        return self.scrape_auto_contributions()

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        accounts = self._client.get_accounts()
        account_id = accounts[0]["accountId"]

        related_security_account_id = self._get_related_security_account(account_id)["accountId"]

        fund_txs, stock_txs = [], []

        try:
            fund_txs = self.scrape_fund_txs(related_security_account_id, registered_txs)
        except Exception as e:
            self._log.error(f"Error getting fund txs: {e}")
            traceback.print_exc()

        try:
            stock_txs = self.scrape_stock_txs(related_security_account_id, registered_txs)
        except Exception as e:
            self._log.error(f"Error getting stock txs: {e}")
            traceback.print_exc()

        investment_txs = fund_txs + stock_txs

        return Transactions(investment=investment_txs)

    def _get_related_security_account(self, account_id: str):
        security_accounts = self._client.get_security_accounts()

        for security_account in security_accounts:
            if security_account["cashAccountId"] == account_id:
                return security_account

    def scrape_account(self):
        accounts = self._client.get_accounts()
        account_id = accounts[0]["accountId"]

        related_security_account_id = self._get_related_security_account(account_id)["accountId"]

        current_interest_rate = None

        try:
            remuneration_details = self._client.get_account_remuneration(account_id)
            current_interest_rate = round(remuneration_details["taePromotion"] / 100, 4)
            if not current_interest_rate:
                current_interest_rate = Dezimal(remuneration_details["remunerationPercentage"])
            else:
                current_interest_rate = round(
                    Dezimal(remuneration_details["calculateTaeAverage"]) / 100, 4
                )
        except Exception as e:
            self._log.error(f"Error getting account remuneration: {e}")

        iban = accounts[0]["iban"]
        alias = accounts[0]["alias"]
        total = Dezimal(accounts[0]["enabledBalance"])
        retained = Dezimal(accounts[0]["withheldBalance"])

        return account_id, related_security_account_id, Account(
            id=uuid4(),
            total=total,
            currency='EUR',
            name=alias,
            iban=iban,
            type=AccountType.CHECKING,
            retained=retained,
            interest=current_interest_rate
        )

    def scrape_cards(self, account_id: str, account: Account):
        raw_cards = self._client.get_cards(account_id=account_id)
        credit_card = next(
            (card for card in raw_cards if card["cardType"] == "CREDIT"), None
        )
        debit_card = next((card for card in raw_cards if card["cardType"] == "DEBIT"), None)

        related_account = account.id

        cards = []
        if credit_card:
            credit_card_tx = self._client.get_card_totals(credit_card["cardId"])
            credit_pan = credit_card["pan"].split(" ")[-1]
            credit_active = credit_card["status"] == "ACTIVATE"

            cards.append(Card(
                id=uuid4(),
                ending=credit_pan,
                currency='EUR',
                type=CardType.CREDIT,
                limit=Dezimal(credit_card_tx["limit"]),
                used=abs(Dezimal(credit_card_tx["consumedMonth"])),
                active=credit_active,
                related_account=related_account
            ))

        if debit_card:
            debit_pan = debit_card["pan"].split(" ")[-1]
            debit_card_tx = self._client.get_card_totals(debit_card["cardId"])
            debit_active = debit_card["status"] == "ACTIVATE"

            cards.append(Card(
                id=uuid4(),
                ending=debit_pan,
                currency='EUR',
                type=CardType.DEBIT,
                limit=Dezimal(debit_card_tx["disposable"]),
                used=abs(Dezimal(debit_card_tx["consumedMonth"])),
                active=debit_active,
                related_account=related_account
            ))

        return cards

    def scrape_deposits(self):
        deposits_raw = self._client.get_deposits()
        if not deposits_raw:
            return None

        deposit_list = [
            Deposit(
                id=uuid4(),
                name=deposit["depositName"],
                amount=round(Dezimal(deposit["amount"]), 2),
                currency='EUR',
                expected_interests=round(Dezimal(deposit["grossInterest"]), 2),
                interest_rate=round(Dezimal(deposit["tae"]) / 100, 4),
                maturity=datetime.strptime(deposit["expirationDate"], ISO_DATE_TIME_FORMAT).date(),
                creation=datetime.strptime(deposit["creationDate"], ISO_DATE_TIME_FORMAT),
            )
            for deposit in deposits_raw
        ]

        total_amount = sum([Dezimal(deposit["amount"]) for deposit in deposits_raw])
        return Deposits(
            total=total_amount,
            expected_interests=sum([Dezimal(deposit["grossInterest"]) for deposit in deposits_raw]),
            weighted_interest_rate=round(
                (sum([Dezimal(deposit["amount"]) * Dezimal(deposit["tae"]) for deposit in deposits_raw])
                 / total_amount) / 100,
                4,
            ),
            details=deposit_list,
        )

    def scrape_investments(self, securities_account_id: str):
        security_account_details = self._client.get_security_account_details(securities_account_id)
        investments = security_account_details["securitiesAccountInvestments"]
        broker_investments = investments.get("BROKER")

        stock_list = []
        total_broker_investment = Dezimal(0)
        if broker_investments:
            stock_list = [
                StockDetail(
                    id=uuid4(),
                    name=stock["investmentName"],
                    ticker=stock.get("ticker", ""),
                    isin=stock["isin"],
                    market=stock["marketCode"],
                    shares=Dezimal(stock["shares"]),
                    initial_investment=round(Dezimal(stock["initialInvestment"]), 4),
                    average_buy_price=round(Dezimal(stock["initialInvestment"]) / Dezimal(stock["shares"]), 4),
                    market_value=round(Dezimal(stock["marketValue"]), 4),
                    currency=stock["liquidationValueCurrency"],
                    type=stock["brokerProductType"],
                    subtype=stock.get("activeTypeCode"),
                )
                for stock in broker_investments["investmentList"]
            ]

            total_broker_investment = sum([stock.initial_investment for stock in stock_list])

        stock_data = StockInvestments(
            investment=round(total_broker_investment, 2),
            market_value=round(Dezimal(broker_investments["totalAmount"]), 4) if broker_investments else 0,
            details=stock_list,
        )

        fund_investments = investments.get("INDEXED_FUND")

        fund_list = []
        total_fund_investment = Dezimal(0)
        if fund_investments:
            fund_list = [
                FundDetail(
                    id=uuid4(),
                    name=fund["investmentName"],
                    isin=fund["isin"],
                    market=fund["marketCode"],
                    shares=fund["shares"],
                    initial_investment=round(Dezimal(fund["initialInvestment"]), 4),
                    average_buy_price=round(Dezimal(fund["initialInvestment"]) / Dezimal(fund["shares"]), 4),
                    market_value=round(Dezimal(fund["marketValue"]), 4),
                    currency=SYMBOL_CURRENCY_MAP.get(
                        fund["liquidationValueCurrency"], fund["liquidationValueCurrency"]
                    ),
                )
                for fund in fund_investments["investmentList"]
            ]

            total_fund_investment = sum([fund.initial_investment for fund in fund_list])

        fund_data = FundInvestments(
            investment=round(total_fund_investment, 2),
            market_value=round(Dezimal(fund_investments["totalAmount"]), 4) if fund_investments else 0,
            details=fund_list,
        )

        deposits = self.scrape_deposits()

        return Investments(
            stocks=stock_data,
            funds=fund_data,
            deposits=deposits,
        )

    def scrape_auto_contributions(self) -> AutoContributions:
        auto_contributions = self._client.get_auto_contributions()

        def get_frequency(frequency) -> ContributionFrequency:
            return {
                "ONE_WEEK": ContributionFrequency.WEEKLY,
                "TWO_WEEKS": ContributionFrequency.BIWEEKLY,
                "ONE_MONTH": ContributionFrequency.MONTHLY,
                "TWO_MONTHS": ContributionFrequency.BIMONTHLY,
                "THREE_MONTHS": ContributionFrequency.QUARTERLY,
                "SIX_MONTHS": ContributionFrequency.SEMIANNUAL,
                "ONE_YEAR": ContributionFrequency.YEARLY,
            }[frequency]

        def get_date(date_str):
            if not date_str:
                return None
            return datetime.strptime(date_str, DATE_FORMAT).date()

        def get_alias(auto_contribution):
            alias = auto_contribution["alias"]
            if alias:
                return alias
            fund_name = auto_contribution["fundName"]
            if fund_name:
                return fund_name
            return None

        periodic_contributions = [
            PeriodicContribution(
                id=uuid4(),
                alias=get_alias(auto_contribution),
                isin=auto_contribution["isin"],
                amount=round(Dezimal(auto_contribution["amount"]), 2),
                since=get_date(auto_contribution["contributionTimeFrame"]["startDate"]),
                until=get_date(auto_contribution["contributionTimeFrame"]["endDate"]),
                frequency=get_frequency(auto_contribution["contributionTimeFrame"]["recurrence"]),
                active=auto_contribution["status"] == "ACTIVE",
                is_real=True
            )
            for auto_contribution in auto_contributions
        ]

        return AutoContributions(
            periodic=periodic_contributions
        )

    def scrape_fund_txs(self, securities_account_id: str, registered_txs: set[str]) -> list[FundTx]:
        raw_fund_orders = self._client.get_fund_orders(securities_account_id=securities_account_id,
                                                       from_date=date.fromisocalendar(2020, 1, 1))

        fund_txs = []
        for order in raw_fund_orders:
            ref = order["reference"]

            if ref in registered_txs:
                continue

            raw_order_details = self._client.get_fund_order_details(ref)
            order_date = datetime.strptime(raw_order_details["orderDate"], ISO_DATE_TIME_FORMAT)
            execution_op = None
            linked_ops = raw_order_details["relatedOperations"]
            if linked_ops:
                execution_op = linked_ops[0]
            execution_date = datetime.strptime(execution_op["executionDate"], ISO_DATE_TIME_FORMAT)

            raw_operation_type = order["operationType"]
            if raw_operation_type == "INVESTMENT_FUNDS_SUBSCRIPTION":
                operation_type = TxType.BUY
            elif "INVESTMENT_FUND_REIMBURSEMENT" in raw_operation_type:
                operation_type = TxType.SELL
            else:
                self._log.warning(f"Unknown operation type: {raw_operation_type}")
                continue

            fund_txs.append(
                FundTx(
                    id=uuid4(),
                    ref=ref,
                    name=order["fundName"].strip(),
                    amount=round(Dezimal(execution_op["grossAmountOperationFundCurrency"]), 2),
                    net_amount=round(Dezimal(execution_op["netAmountFundCurrency"]), 2),
                    currency=order["currency"],
                    type=operation_type,
                    order_date=order_date,
                    entity=MY_INVESTOR,
                    isin=order["isin"],
                    shares=round(Dezimal(raw_order_details["executedShares"]), 4),
                    price=round(Dezimal(execution_op["liquidationValue"]), 4),
                    market=order["market"],
                    fees=round(Dezimal(execution_op["commissions"]), 2),
                    retentions=Dezimal(0),
                    date=execution_date,
                    product_type=ProductType.FUND,
                    is_real=True
                )
            )

        return fund_txs

    def scrape_stock_txs(self, securities_account_id: str, registered_txs: set[str]) -> list[StockTx]:
        raw_stock_orders = []

        # Both v1 & v2 stock order history endpoint are failing for some dates, we retry since current year
        try:
            raw_stock_orders += self._client.get_stock_orders(securities_account_id=securities_account_id,
                                                              from_date=date.fromisocalendar(2020, 1, 1),
                                                              to_date=date.today().replace(year=date.today().year - 1,
                                                                                           month=9, day=1),
                                                              status=None)

            raw_stock_orders += self._client.get_stock_orders(securities_account_id=securities_account_id,
                                                              from_date=date.today().replace(year=2024, month=9, day=1),
                                                              to_date=date.fromisocalendar(date.today().year, 1, 1),
                                                              status=None)
        finally:
            raw_stock_orders += self._client.get_stock_orders(securities_account_id=securities_account_id,
                                                              from_date=date.fromisocalendar(date.today().year, 1, 2),
                                                              status=None)

        stock_txs = []
        for order in raw_stock_orders:
            ref = order["id"]

            if ref in registered_txs:
                continue

            raw_order_details = self._client.get_stock_order_details(ref)
            order_date = datetime.strptime(raw_order_details["orderDate"], ISO_DATE_TIME_FORMAT)

            raw_operation_type = order["operation"]
            if "COMPRA" in raw_operation_type:
                operation_type = TxType.BUY
            elif "VENTA" in raw_operation_type:
                operation_type = TxType.SELL
            else:
                self._log.warning(f"Unknown operation type: {raw_operation_type}")
                continue

            if not raw_order_details.get("executedShares"):
                continue

            amount = round(Dezimal(raw_order_details["grossAmountOperationCurrency"]), 2)
            net_amount = round(Dezimal(raw_order_details["netAmountCurrency"]), 2)

            fees = Dezimal(0)
            if operation_type == TxType.BUY:
                # Financial Tx Tax not included in "comisionCorretaje", "comisionMiembroMercado" and "costeCanon"
                fees = net_amount - amount
            elif operation_type == TxType.SELL:
                fees = Dezimal(raw_order_details["tradeCommissions"]) + Dezimal(raw_order_details["otherCommissions"])

            execution_date = datetime.strptime(raw_order_details["executionDate"], ISO_DATE_TIME_FORMAT)

            stock_txs.append(
                StockTx(
                    id=uuid4(),
                    ref=ref,
                    name=order["toolName"].strip(),
                    ticker=order["ticker"],
                    amount=amount,
                    net_amount=net_amount,
                    currency=order["currency"],
                    type=operation_type,
                    order_date=order_date,
                    entity=MY_INVESTOR,
                    isin=raw_order_details["instrumentIsin"],
                    shares=round(Dezimal(raw_order_details["executedShares"]), 4),
                    price=round(Dezimal(raw_order_details["priceCurrency"]), 4),
                    market=order["marketId"],
                    fees=round(fees, 2),
                    retentions=Dezimal(0),
                    date=execution_date,
                    product_type=ProductType.STOCK_ETF,
                    is_real=True,
                    linked_tx=None
                )
            )

        return stock_txs
