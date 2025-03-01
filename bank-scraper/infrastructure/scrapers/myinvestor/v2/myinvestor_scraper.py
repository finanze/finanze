import logging
import traceback
from datetime import date, datetime

from application.ports.entity_scraper import EntityScraper
from domain.auto_contributions import PeriodicContribution, ContributionFrequency, AutoContributions
from domain.currency_symbols import CURRENCY_SYMBOL_MAP, SYMBOL_CURRENCY_MAP
from domain.financial_entity import Entity
from domain.global_position import Account, AccountAdditionalData, Cards, Card, StockDetail, StockInvestments, \
    FundDetail, \
    FundInvestments, Investments, GlobalPosition, PositionAdditionalData, \
    Deposit, Deposits, SourceType
from domain.transactions import Transactions, FundTx, TxType, StockTx, ProductType
from infrastructure.scrapers.myinvestor.v2.myinvestor_client import MyInvestorAPIV2Client

DATE_FORMAT = "%Y-%m-%d"
ISO_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class MyInvestorScraperV2(EntityScraper):

    def __init__(self):
        self._client = MyInvestorAPIV2Client()
        self._log = logging.getLogger(__name__)

    async def login(self, credentials: tuple, **kwargs) -> dict:
        username, password = credentials
        return self._client.login(username, password)

    async def global_position(self) -> GlobalPosition:
        maintenance = self._client.check_maintenance()

        account_id, securities_account_id, account_data = self.scrape_account()

        cards_data = self.scrape_cards(account_id)

        investments_data = self.scrape_investments(securities_account_id)

        return GlobalPosition(
            account=account_data,
            cards=cards_data,
            investments=investments_data,
            additionalData=PositionAdditionalData(maintenance=len(maintenance) > 0),
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
        avg_interest_rate = None
        remuneration_type = None

        try:
            remuneration_details = self._client.get_account_remuneration(account_id)
            current_interest_rate = round(remuneration_details["taePromotion"] / 100, 4)
            avg_interest_rate = round(
                remuneration_details["calculateTaeAverage"] / 100, 4
            )
            remuneration_type = remuneration_details["remunerationType"]
        except Exception as e:
            self._log.error(f"Error getting account remuneration: {e}")

        return account_id, related_security_account_id, Account(
            total=accounts[0]["enabledBalance"],
            retained=accounts[0]["withheldBalance"],
            interest=current_interest_rate,
            additionalData=AccountAdditionalData(
                averageInterestRate=avg_interest_rate,
                remunerationType=remuneration_type,
            ),
        )

    def scrape_cards(self, account_id: str):
        cards = self._client.get_cards(account_id=account_id)
        credit_card = next(
            (card for card in cards if card["cardType"] == "CREDIT"), None
        )
        debit_card = next((card for card in cards if card["cardType"] == "DEBIT"), None)

        credit_card_tx = self._client.get_card_totals(credit_card["cardId"])
        debit_card_tx = self._client.get_card_totals(debit_card["cardId"])

        return Cards(
            credit=Card(limit=credit_card_tx["limit"], used=abs(credit_card_tx["consumedMonth"])),
            debit=Card(limit=debit_card_tx["limit"], used=abs(debit_card_tx["consumedMonth"])),
        )

    def scrape_deposits(self):
        deposits_raw = self._client.get_deposits()
        if not deposits_raw:
            return None

        deposit_list = [
            Deposit(
                name=deposit["depositName"],
                amount=round(deposit["amount"], 2),
                totalInterests=round(deposit["grossInterest"], 2),
                interestRate=round(deposit["tae"] / 100, 4),
                maturity=datetime.strptime(deposit["expirationDate"], ISO_DATE_TIME_FORMAT).date(),
                creation=datetime.strptime(deposit["creationDate"], ISO_DATE_TIME_FORMAT).date(),
            )
            for deposit in deposits_raw
        ]

        total_amount = sum([deposit["amount"] for deposit in deposits_raw])
        return Deposits(
            total=total_amount,
            totalInterests=sum([deposit["grossInterest"] for deposit in deposits_raw]),
            weightedInterestRate=round(
                (sum([deposit["amount"] * deposit["tae"] for deposit in deposits_raw])
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
        total_broker_investment = 0
        if broker_investments:
            stock_list = [
                StockDetail(
                    name=stock["investmentName"],
                    ticker=stock.get("ticker", ""),
                    isin=stock["isin"],
                    market=stock["marketCode"],
                    shares=stock["shares"],
                    initialInvestment=round(stock["initialInvestment"], 4),
                    averageBuyPrice=round(stock["initialInvestment"] / stock["shares"], 4),
                    marketValue=round(stock["marketValue"], 4),
                    currency=stock["liquidationValueCurrency"],
                    currencySymbol=CURRENCY_SYMBOL_MAP.get(stock["liquidationValueCurrency"],
                                                           stock["liquidationValueCurrency"]),
                    type=stock["brokerProductType"],
                    subtype=stock.get("activeTypeCode"),
                )
                for stock in broker_investments["investmentList"]
            ]

            total_broker_investment = sum([stock.initialInvestment for stock in stock_list])

        stock_data = StockInvestments(
            initialInvestment=round(total_broker_investment, 4),
            marketValue=round(broker_investments["totalAmount"], 4) if broker_investments else 0,
            details=stock_list,
        )

        fund_investments = investments.get("INDEXED_FUND")

        fund_list = []
        total_fund_investment = 0
        if fund_investments:
            fund_list = [
                FundDetail(
                    name=fund["investmentName"],
                    isin=fund["isin"],
                    market=fund["marketCode"],
                    shares=fund["shares"],
                    initialInvestment=round(fund["initialInvestment"], 4),
                    averageBuyPrice=round(fund["initialInvestment"] / fund["shares"], 4),
                    marketValue=round(fund["marketValue"], 4),
                    currency=SYMBOL_CURRENCY_MAP.get(
                        fund["liquidationValueCurrency"], fund["liquidationValueCurrency"]
                    ),
                    currencySymbol=fund["liquidationValueCurrency"],
                    lastUpdate=datetime.strptime(fund["liquidationValueDate"], ISO_DATE_TIME_FORMAT).date(),
                )
                for fund in fund_investments["investmentList"]
            ]

            total_fund_investment = sum([fund.initialInvestment for fund in fund_list])

        fund_data = FundInvestments(
            initialInvestment=round(total_fund_investment, 4),
            marketValue=round(fund_investments["totalAmount"], 4) if fund_investments else 0,
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
                alias=get_alias(auto_contribution),
                isin=auto_contribution["isin"],
                amount=round(auto_contribution["amount"], 2),
                since=get_date(auto_contribution["contributionTimeFrame"]["startDate"]),
                until=get_date(auto_contribution["contributionTimeFrame"]["endDate"]),
                frequency=get_frequency(auto_contribution["contributionTimeFrame"]["recurrence"]),
                active=auto_contribution["status"] == "ACTIVE",
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
            elif "REIMB" in raw_operation_type:  # ??
                operation_type = TxType.SELL
            else:
                self._log.warning(f"Unknown operation type: {raw_operation_type}")
                continue

            fund_txs.append(
                FundTx(
                    id=ref,
                    name=order["fundName"].strip(),
                    amount=round(execution_op["grossAmountOperationFundCurrency"], 2),
                    netAmount=round(execution_op["netAmountFundCurrency"], 2),
                    currency=order["currency"],
                    currencySymbol=CURRENCY_SYMBOL_MAP.get(order["currency"], order["currency"]),
                    type=operation_type,
                    orderDate=order_date,
                    entity=Entity.MY_INVESTOR,
                    isin=order["isin"],
                    shares=round(raw_order_details["executedShares"], 4),
                    price=round(execution_op["liquidationValue"], 4),
                    market=order["market"],
                    fees=round(execution_op["commissions"], 2),
                    retentions=0,
                    date=execution_date,
                    productType=ProductType.FUND,
                    sourceType=SourceType.REAL
                )
            )

        return fund_txs

    def scrape_stock_txs(self, securities_account_id: str, registered_txs: set[str]) -> list[StockTx]:
        try:
            raw_stock_orders = self._client.get_stock_orders(securities_account_id=securities_account_id,
                                                             from_date=date.fromisocalendar(2020, 1, 1),
                                                             status=None)
        except:
            # Both v1 & v2 stock order history endpoint are failing for some dates, we retry since 2025
            raw_stock_orders = self._client.get_stock_orders(securities_account_id=securities_account_id,
                                                             from_date=date.fromisocalendar(2025, 1, 1),
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

            amount = round(raw_order_details["grossAmountOperationCurrency"], 2)
            net_amount = round(raw_order_details["netAmountCurrency"], 2)

            fees = 0
            if operation_type == TxType.BUY:
                # Financial Tx Tax not included in "comisionCorretaje", "comisionMiembroMercado" and "costeCanon"
                fees = net_amount - amount
            elif operation_type == TxType.SELL:
                fees = raw_order_details["tradeCommissions"] + raw_order_details["otherCommissions"]

            execution_date = datetime.strptime(raw_order_details["executionDate"], ISO_DATE_TIME_FORMAT)

            stock_txs.append(
                StockTx(
                    id=ref,
                    name=order["toolName"].strip(),
                    ticker=order["ticker"],
                    amount=amount,
                    netAmount=net_amount,
                    currency=order["currency"],
                    currencySymbol=CURRENCY_SYMBOL_MAP.get(order["currency"], order["currency"]),
                    type=operation_type,
                    orderDate=order_date,
                    entity=Entity.MY_INVESTOR,
                    isin=raw_order_details["instrumentIsin"],
                    shares=round(raw_order_details["executedShares"], 4),
                    price=round(raw_order_details["priceCurrency"], 4),
                    market=order["marketId"],
                    fees=round(fees, 2),
                    retentions=0,
                    date=execution_date,
                    productType=ProductType.STOCK_ETF,
                    sourceType=SourceType.REAL,
                    linkedTx=None
                )
            )

        return stock_txs
