import logging
import traceback
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.constants import CAPITAL_GAINS_BASE_TAX
from domain.currency_symbols import SYMBOL_CURRENCY_MAP
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    AssetType,
    Card,
    Cards,
    CardType,
    Deposit,
    Deposits,
    EquityType,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    GlobalPosition,
    ProductPositions,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.native_entities import MY_INVESTOR
from domain.transactions import (
    AccountTx,
    DepositTx,
    FundPortfolioTx,
    FundTx,
    StockTx,
    Transactions,
    TxType,
)
from infrastructure.client.entity.financial.myinvestor.v2.myinvestor_client import (
    MyInvestorAPIV2Client,
)

DATE_FORMAT = "%Y-%m-%d"
ISO_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

FUND_INVESTMENT_TXS = [
    "INVESTMENT_FUNDS_SUBSCRIPTION",
    "INVESTMENT_FUNDS_SUBSCRIPTION_SF",
]
FUND_TRANSFER_IN_TXS = [
    "INTERNAL_TRANSFER_SUBSCRIPTION",
    "EXTERNAL_TRANSFER_SUBSCRIPTION",
]
FUND_REIMBURSEMENT_TXS = [
    "INVESTMENT_FUND_REIMBURSEMENT",
    "INVESTMENT_FUND_REIMBURSEMENT_SF",
]
FUND_TRANSFER_OUT_TXS = [
    "INTERNAL_TRANSFER_REIMBURSEMENT",
    "EXTERNAL_TRANSFER_REIMBURSEMENT",
]

CONTRIBUTION_FREQUENCY = {
    "ONE_WEEK": ContributionFrequency.WEEKLY,
    "TWO_WEEKS": ContributionFrequency.BIWEEKLY,
    "ONE_MONTH": ContributionFrequency.MONTHLY,
    "TWO_MONTHS": ContributionFrequency.BIMONTHLY,
    "THREE_MONTHS": ContributionFrequency.QUARTERLY,
    "SIX_MONTHS": ContributionFrequency.SEMIANNUAL,
    "ONE_YEAR": ContributionFrequency.YEARLY,
}

ACCOUNT_TYPE_MAP = {
    "CASH_ACCOUNT": AccountType.CHECKING,
    "CASH_PORTFOLIO": AccountType.FUND_PORTFOLIO,
}

FUND_CATEGORIES = ["INDEXED_FUND", "FUND"]

BEGINNING = date.fromisocalendar(2018, 1, 1)

ACCOUNT_TX_FETCH_STEP = relativedelta(months=2)
STOCKS_TX_FETCH_STEP = relativedelta(months=4)


def _get_stock_investments(broker_investments) -> StockInvestments:
    stock_list = []
    if broker_investments:
        for stock in broker_investments["investmentList"]:
            product_type = (
                EquityType.STOCK
                if stock["brokerProductType"] == "RV"
                else EquityType.ETF
            )
            stock_list.append(
                StockDetail(
                    id=uuid4(),
                    name=stock["investmentName"],
                    ticker=stock.get("ticker", ""),
                    isin=stock["isin"],
                    market=stock["marketCode"],
                    shares=Dezimal(stock["shares"]),
                    initial_investment=round(Dezimal(stock["initialInvestment"]), 4),
                    average_buy_price=round(
                        Dezimal(stock["initialInvestment"]) / Dezimal(stock["shares"]),
                        4,
                    ),
                    market_value=round(Dezimal(stock["marketValue"]), 4),
                    currency=stock["liquidationValueCurrency"],
                    type=product_type,
                    subtype=stock.get("activeTypeCode"),
                )
            )

    return StockInvestments(stock_list)


def _map_deposit_tx(
    ref, tx_type, name, amount, net, retentions, tx_date, currency
) -> Optional[DepositTx]:
    return DepositTx(
        id=uuid4(),
        ref=ref,
        name=name,
        amount=round(amount, 2),
        currency=currency,
        type=tx_type,
        date=tx_date,
        entity=MY_INVESTOR,
        product_type=ProductType.DEPOSIT,
        fees=Dezimal(0),
        retentions=round(retentions, 2),
        net_amount=round(net, 2),
        source=DataSource.REAL,
    )


def _map_account_tx(ref, name, amount, currency, tx_date, retentions):
    amount = round(amount, 2)
    retentions = round(retentions, 2)
    net_amount = amount - retentions
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name=name,
        amount=amount,
        currency=currency,
        type=TxType.INTEREST,
        product_type=ProductType.ACCOUNT,
        date=tx_date,
        entity=MY_INVESTOR,
        fees=Dezimal(0),
        retentions=retentions,
        net_amount=net_amount,
        interest_rate=None,
        avg_balance=None,
        source=DataSource.REAL,
    )


class MyInvestorFetcherV2(FinancialEntityFetcher):
    def __init__(self):
        self._client = MyInvestorAPIV2Client()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        two_factor = login_params.two_factor

        username, password = credentials["user"], credentials["password"]
        process_id, code = None, None
        if two_factor:
            process_id, code = two_factor.process_id, two_factor.code

        return self._client.login(
            username,
            password,
            login_options=login_params.options,
            process_id=process_id,
            code=code,
        )

    async def global_position(self) -> GlobalPosition:
        # maintenance = self._client.check_maintenance()

        account_entries = self.fetch_accounts()
        accounts = [account for _, account, _ in account_entries]

        cards_data = self.fetch_cards(account_entries)

        product_positions = self.fetch_investments(account_entries)

        product_positions[ProductType.ACCOUNT] = Accounts(accounts)
        product_positions[ProductType.CARD] = Cards(cards_data)

        return GlobalPosition(
            id=uuid4(),
            entity=MY_INVESTOR,
            products=product_positions,
        )

    async def auto_contributions(self) -> AutoContributions:
        return self.fetch_auto_contributions()

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        accounts = self._get_active_owned_accounts()

        target_accounts = [
            account
            for account in accounts
            if account["accountType"] in ["CASH_ACCOUNT", "CASH_PORTFOLIO"]
        ]

        investment_txs = []
        account_txs = []

        for account in target_accounts:
            account_id = account["accountId"]
            creation_date = datetime.fromisoformat(account["creationDate"]).date()
            related_security_account_id = self._get_related_security_account(
                account_id
            )["accountId"]
            investment_txs += self._get_investment_txs(
                registered_txs, related_security_account_id, creation_date
            )

            account_related_txs = self._classify_account_txs(
                account, registered_txs, related_security_account_id, creation_date
            )
            investment_txs += account_related_txs["deposit"]
            investment_txs += account_related_txs["portfolio"]
            account_txs += account_related_txs["interests"]

        return Transactions(investment=investment_txs, account=account_txs)

    def _get_investment_txs(
        self, registered_txs, related_security_account_id, min_date: date
    ):
        fund_txs, stock_txs = [], []

        try:
            fund_txs = self.fetch_fund_txs(
                related_security_account_id, registered_txs, min_date
            )
        except Exception as e:
            self._log.error(f"Error getting fund txs: {e}")
            traceback.print_exc()

        try:
            stock_txs = self.fetch_stock_txs(
                related_security_account_id, registered_txs, min_date
            )
        except Exception as e:
            self._log.error(f"Error getting stock txs: {e}")
            traceback.print_exc()
        investment_txs = fund_txs + stock_txs

        return investment_txs

    def _get_related_security_account(self, account_id: str) -> Optional[dict]:
        security_accounts = self._client.get_security_accounts()

        for security_account in security_accounts:
            if security_account["cashAccountId"] == account_id:
                return security_account

        return None

    def _get_active_owned_accounts(self) -> list[dict]:
        found = []
        accounts = self._client.get_cash_accounts()

        for account in accounts:
            active = account.get("status") == "ACTIVE" or account.get("active")
            if not active:
                continue

            if account["accountType"] not in ACCOUNT_TYPE_MAP:
                continue

            holders = account["holders"]
            user_is_owner = any([holder.get("me") for holder in holders])
            if not user_is_owner:
                continue

            found.append(account)

        return found

    def _classify_account_txs(
        self, account: dict, registered_txs, related_security_account_id, min_date: date
    ):
        account_id = account["accountId"]
        account_type = account.get("accountType")
        portfolio_account_details = {}

        if account_type == "CASH_PORTFOLIO":
            portfolio_account_details = self._client.get_security_account_details(
                related_security_account_id
            )

        deposit_txs = []
        interest_txs = []
        portfolio_txs = []
        result = {
            "deposit": deposit_txs,
            "interests": interest_txs,
            "portfolio": portfolio_txs,
        }

        to_date = from_date = date.today()
        from_date += timedelta(days=1)
        while from_date > min_date:
            from_date -= ACCOUNT_TX_FETCH_STEP
            raw_txs = self._client.get_account_movements(
                account_id, from_date, to_date
            )["flowList"]

            for tx in raw_txs:
                ref = tx["reference"]
                if ref in registered_txs:
                    return result

                tx_class = tx["operationClass"]
                raw_tx_type = tx["operationType"]
                tx_date = datetime.fromtimestamp(tx["operationDate"] / 1000).replace(
                    tzinfo=tzlocal()
                )
                currency = tx["currency"]
                name = tx["concept"].strip()
                amount = abs(Dezimal(tx["amount"]))

                if tx_class == "MOVIMIENTOS DEPOSITOS":
                    if raw_tx_type == "ABONO LIQUIDAC DEPO":
                        related_deposit_data = tx.get("depositSettlementDetails")
                        if not related_deposit_data:
                            continue

                        deposit_amount = Dezimal(related_deposit_data["amount"])
                        net_interest = Dezimal(
                            related_deposit_data["netInterestAmount"]
                        )
                        interest = Dezimal(related_deposit_data["grossInterestAmount"])
                        retentions = interest - net_interest

                        deposit_txs.append(
                            _map_deposit_tx(
                                ref,
                                TxType.REPAYMENT,
                                name,
                                deposit_amount,
                                deposit_amount,
                                Dezimal(0),
                                tx_date,
                                currency,
                            )
                        )

                        deposit_txs.append(
                            _map_deposit_tx(
                                ref + "_INT",
                                TxType.INTEREST,
                                name,
                                interest,
                                net_interest,
                                retentions,
                                tx_date,
                                currency,
                            )
                        )

                    elif raw_tx_type == "CARGO P/DEPOSITO":
                        deposit_txs.append(
                            _map_deposit_tx(
                                ref,
                                TxType.INVESTMENT,
                                name,
                                amount,
                                amount,
                                Dezimal(0),
                                tx_date,
                                currency,
                            )
                        )

                elif tx_class == "LIQUIDACION INTERESES CUENTA":
                    if (
                        raw_tx_type == "LIQUIDAC. INTERESES"
                    ):  # Old one, retention is already deducted
                        net_amount = amount
                        amount = net_amount / (1 - CAPITAL_GAINS_BASE_TAX)
                        retentions = amount - net_amount
                        interest_txs.append(
                            _map_account_tx(
                                ref, name, amount, currency, tx_date, retentions
                            )
                        )

                elif tx_class == "ME":
                    if raw_tx_type == "RETE.LIQUIDA":
                        pass

                elif tx_class == "0":
                    if raw_tx_type == "INTERESES S/F":
                        retentions = amount * CAPITAL_GAINS_BASE_TAX
                        interest_txs.append(
                            _map_account_tx(
                                ref, name, amount, currency, tx_date, retentions
                            )
                        )

                # Portfolio management / custody fees (only for portfolio accounts)
                elif (
                    account_type == "CASH_PORTFOLIO"
                    and "COMISION" in raw_tx_type.upper()
                ):
                    account_iban = account.get("iban")
                    fee_amount = abs(Dezimal(tx["amount"]))
                    portfolio_name = portfolio_account_details.get("portfolioName")
                    if fee_amount > 0:
                        portfolio_txs.append(
                            FundPortfolioTx(
                                id=uuid4(),
                                ref=ref,
                                name=name,
                                amount=fee_amount,
                                currency=currency,
                                type=TxType.FEE,
                                date=tx_date,
                                entity=MY_INVESTOR,
                                source=DataSource.REAL,
                                product_type=ProductType.FUND_PORTFOLIO,
                                fees=fee_amount,
                                portfolio_name=portfolio_name,
                                iban=account_iban,
                            )
                        )

            to_date -= ACCOUNT_TX_FETCH_STEP

        return result

    def fetch_accounts(self) -> list[tuple[dict, Account, dict]]:
        accounts = self._get_active_owned_accounts()

        accounts_with_security = []

        for account in accounts:
            account_type = ACCOUNT_TYPE_MAP[account["accountType"]]
            account_id = account["accountId"]
            security_account = self._get_related_security_account(account_id)
            current_interest_rate = self._get_account_remuneration(account_id)

            iban = account["iban"]
            alias = account["alias"]
            total = Dezimal(account["enabledBalance"])
            retained = Dezimal(account["withheldBalance"])

            entry = (
                account,
                Account(
                    id=uuid4(),
                    total=total,
                    currency="EUR",
                    name=alias,
                    iban=iban,
                    type=account_type,
                    retained=retained,
                    interest=current_interest_rate,
                ),
                security_account,
            )

            accounts_with_security.append(entry)

        return accounts_with_security

    def _get_account_remuneration(self, account_id) -> Dezimal:
        current_interest_rate = Dezimal(0)
        try:
            remuneration_details = self._client.get_account_remuneration(account_id)
            current_interest_rate = round(remuneration_details["taePromotion"] / 100, 4)
            if not current_interest_rate:
                current_interest_rate = round(
                    Dezimal(remuneration_details["remunerationPercentage"]) / 100, 4
                )
            else:
                current_interest_rate = round(
                    Dezimal(remuneration_details["calculateTaeAverage"]) / 100, 4
                )
        except Exception as e:
            self._log.error(f"Error getting account remuneration: {e}")

        return current_interest_rate

    def fetch_cards(self, accounts: list[tuple]) -> list[Card]:
        cards = []

        for raw_account, account, _ in accounts:
            account_id = raw_account["accountId"]
            raw_cards = self._client.get_cards(account_id=account_id)
            credit_card = next(
                (card for card in raw_cards if card["cardType"] == "CREDIT"), None
            )
            debit_card = next(
                (card for card in raw_cards if card["cardType"] == "DEBIT"), None
            )

            if credit_card:
                credit_card_tx = self._client.get_card_totals(credit_card["cardId"])
                credit_pan = credit_card["pan"].split(" ")[-1]
                credit_active = credit_card["status"] == "ACTIVATE"
                credit_limit = credit_card_tx.get("limit")
                used = credit_card_tx.get("consumedMonth") or 0

                cards.append(
                    Card(
                        id=uuid4(),
                        ending=credit_pan,
                        currency="EUR",
                        type=CardType.CREDIT,
                        limit=Dezimal(credit_limit) if credit_limit else None,
                        used=abs(Dezimal(used)),
                        active=credit_active,
                        related_account=account.id,
                    )
                )

            if debit_card:
                debit_pan = debit_card["pan"].split(" ")[-1]
                debit_card_totals = self._client.get_card_totals(debit_card["cardId"])
                debit_active = debit_card["status"] == "ACTIVATE"
                disposable = debit_card_totals.get("disposable")
                used = debit_card_totals.get("consumedMonth") or 0

                cards.append(
                    Card(
                        id=uuid4(),
                        ending=debit_pan,
                        currency="EUR",
                        type=CardType.DEBIT,
                        limit=Dezimal(disposable) if disposable else None,
                        used=abs(Dezimal(used)),
                        active=debit_active,
                        related_account=account.id,
                    )
                )

        return cards

    def fetch_deposits(self) -> Deposits:
        deposits_raw = self._client.get_deposits()
        if not deposits_raw:
            return Deposits([])

        deposit_list = [
            Deposit(
                id=uuid4(),
                name=deposit["depositName"],
                amount=round(Dezimal(deposit["amount"]), 2),
                currency="EUR",
                expected_interests=round(Dezimal(deposit["grossInterest"]), 2),
                interest_rate=round(Dezimal(deposit["tae"]) / 100, 4),
                maturity=datetime.strptime(
                    deposit["expirationDate"], ISO_DATE_TIME_FORMAT
                ).date(),
                creation=datetime.strptime(
                    deposit["creationDate"], ISO_DATE_TIME_FORMAT
                ),
            )
            for deposit in deposits_raw
        ]

        return Deposits(deposit_list)

    def fetch_investments(self, account_entries: list[tuple]) -> ProductPositions:
        deposits = self.fetch_deposits()

        main_security_account = next(
            (
                security_account
                for raw_account, _, security_account in account_entries
                if raw_account["accountType"] == "CASH_ACCOUNT"
            ),
            None,
        )

        security_account_id = main_security_account["accountId"]
        security_account_details = self._client.get_security_account_details(
            security_account_id
        )
        investments = security_account_details["securitiesAccountInvestments"]

        broker_investments = investments.get("BROKER")
        stock_data = _get_stock_investments(broker_investments)

        fund_data = self._get_fund_investments(investments, security_account_id)

        portfolio_cash_accounts = []
        for raw_account, acc, security_account in account_entries:
            if raw_account["accountType"] != "CASH_PORTFOLIO":
                continue

            portfolio_security_account_id = security_account["accountId"]
            portfolio_account_details = self._client.get_security_account_details(
                portfolio_security_account_id
            )
            portfolio_account_investments = portfolio_account_details[
                "securitiesAccountInvestments"
            ]

            portfolio_id = uuid4()

            portfolio_fund_data = self._get_fund_investments(
                portfolio_account_investments,
                portfolio_security_account_id,
                portfolio_id,
            )

            market_value = Dezimal(portfolio_account_details["marketValue"])
            total_invested = Dezimal(portfolio_account_details["totalInvested"])

            portfolio_cash_accounts.append(
                FundPortfolio(
                    id=portfolio_id,
                    name=portfolio_account_details["portfolioName"],
                    currency="EUR",
                    initial_investment=total_invested,
                    market_value=market_value,
                    account_id=acc.id,
                )
            )

            fund_data = fund_data + portfolio_fund_data

        return {
            ProductType.STOCK_ETF: stock_data,
            ProductType.FUND: fund_data,
            ProductType.FUND_PORTFOLIO: FundPortfolios(portfolio_cash_accounts),
            ProductType.DEPOSIT: deposits,
        }

    def _map_periodic_contribution(self, auto_contribution):
        raw_frequency = auto_contribution["contributionTimeFrame"]["recurrence"]
        frequency = CONTRIBUTION_FREQUENCY.get(raw_frequency)
        if not frequency:
            self._log.warning(f"Unknown contribution frequency: {raw_frequency}")
            return None

        def get_date(date_str):
            if not date_str:
                return None
            return datetime.strptime(date_str, DATE_FORMAT).date()

        target_account_alias = auto_contribution.get("toAccountAlias")
        fund_name = auto_contribution.get("fundName")
        isin = auto_contribution.get("isin")
        target_cash_account = auto_contribution.get("toAccountIban")
        alias = auto_contribution.get("alias")

        target_name = fund_name or target_account_alias
        alias = alias or target_name
        target = isin or target_cash_account
        target_type = (
            ContributionTargetType.FUND
            if fund_name
            else ContributionTargetType.FUND_PORTFOLIO
        )

        return PeriodicContribution(
            id=uuid4(),
            alias=alias,
            target=target,
            target_name=target_name,
            target_type=target_type,
            amount=round(Dezimal(auto_contribution["amount"]), 2),
            currency=SYMBOL_CURRENCY_MAP.get(auto_contribution["currency"], "EUR"),
            since=get_date(auto_contribution["contributionTimeFrame"]["startDate"]),
            until=get_date(auto_contribution["contributionTimeFrame"]["endDate"]),
            frequency=frequency,
            active=auto_contribution["status"] == "ACTIVE",
            source=DataSource.REAL,
        )

    def fetch_auto_contributions(self) -> AutoContributions:
        auto_contributions = self._client.get_auto_contributions()

        periodic_contributions = [
            self._map_periodic_contribution(auto_contribution)
            for auto_contribution in auto_contributions
            if auto_contribution["contributionType"] == "ONE_DATE"
        ]

        return AutoContributions(periodic=periodic_contributions)

    def fetch_fund_txs(
        self, securities_account_id: str, registered_txs: set[str], min_date: date
    ) -> list[FundTx]:
        raw_fund_orders = self._client.get_fund_orders(
            securities_account_id=securities_account_id, from_date=min_date
        )

        fund_txs = []
        for order in raw_fund_orders:
            ref = order["reference"]

            if ref in registered_txs:
                continue

            raw_operation_type = order["operationType"]
            if raw_operation_type in FUND_INVESTMENT_TXS:
                operation_type = TxType.BUY
            elif raw_operation_type in FUND_REIMBURSEMENT_TXS:
                operation_type = TxType.SELL
            elif raw_operation_type in FUND_TRANSFER_IN_TXS:
                operation_type = TxType.TRANSFER_IN
            elif raw_operation_type in FUND_TRANSFER_OUT_TXS:
                operation_type = TxType.TRANSFER_OUT
            elif raw_operation_type in {"IIC_SWITCH_REGISTRATION"}:
                operation_type = TxType.SWITCH_TO
            elif raw_operation_type in {"IIC_SWITCH_DEREGISTRATION"}:
                operation_type = TxType.SWITCH_FROM
            else:
                self._log.warning(
                    f"Unknown operation type {raw_operation_type} for tx {ref}"
                )
                continue

            raw_order_details = self._client.get_fund_order_details(
                securities_account_id, ref
            )
            order_date = datetime.strptime(
                raw_order_details["orderDate"], ISO_DATE_TIME_FORMAT
            )
            execution_op = None
            linked_ops = raw_order_details["relatedOperations"]
            if linked_ops:
                execution_op = linked_ops[0]
            execution_date = datetime.strptime(
                execution_op["executionDate"], ISO_DATE_TIME_FORMAT
            )

            fund_txs.append(
                FundTx(
                    id=uuid4(),
                    ref=ref,
                    name=order["fundName"].strip(),
                    amount=round(
                        Dezimal(execution_op["grossAmountOperationFundCurrency"]), 2
                    ),
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
                    fund_type=FundType.MUTUAL_FUND,
                    source=DataSource.REAL,
                )
            )

        return fund_txs

    def fetch_stock_txs(
        self, securities_account_id: str, registered_txs: set[str], min_date: date
    ) -> list[StockTx]:
        stock_txs = []

        to_date = from_date = date.today()
        from_date += timedelta(days=1)
        while from_date > min_date:
            from_date -= STOCKS_TX_FETCH_STEP
            raw_txs = self._client.get_stock_orders(
                securities_account_id=securities_account_id,
                from_date=from_date,
                to_date=to_date,
                status=None,
            )

            for order in raw_txs:
                ref = order["id"]

                if ref in registered_txs:
                    continue

                raw_operation_type = order["operation"]
                if (
                    "COMPRA" in raw_operation_type
                    or raw_operation_type == "PURCHASE_VARIABLE_INCOME_CASH"
                ):
                    operation_type = TxType.BUY
                elif (
                    "VENTA" in raw_operation_type
                    or raw_operation_type == "SALE_VARIABLE_INCOME_CASH"
                ):
                    operation_type = TxType.SELL
                else:
                    self._log.warning(
                        f"Unknown operation type {raw_operation_type} for tx {ref}"
                    )
                    continue

                raw_order_details = self._client.get_stock_order_details(ref)
                order_date = datetime.strptime(
                    raw_order_details["orderDate"], ISO_DATE_TIME_FORMAT
                )

                if not raw_order_details.get("executedShares"):
                    continue

                amount = round(
                    Dezimal(raw_order_details["grossAmountOperationCurrency"]), 2
                )
                net_amount = round(Dezimal(raw_order_details["netAmountCurrency"]), 2)

                fees = Dezimal(0)
                if operation_type == TxType.BUY:
                    # Financial Tx Tax not included in "comisionCorretaje", "comisionMiembroMercado" and "costeCanon"
                    fees = net_amount - amount
                elif operation_type == TxType.SELL:
                    fees = Dezimal(raw_order_details["tradeCommissions"]) + Dezimal(
                        raw_order_details["otherCommissions"]
                    )

                execution_date = datetime.strptime(
                    raw_order_details["executionDate"], ISO_DATE_TIME_FORMAT
                )

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
                        source=DataSource.REAL,
                        linked_tx=None,
                    )
                )

            to_date -= STOCKS_TX_FETCH_STEP

        return stock_txs

    def _get_fund_investments(
        self, investments, security_account_id, portfolio_id=None
    ) -> FundInvestments:
        fund_list = []

        for fund_category in FUND_CATEGORIES:
            category_investment_data = investments.get(fund_category)
            if not category_investment_data:
                continue

            for fund in category_investment_data.get("investmentList", []):
                isin = fund.get("isin")
                fund_details = self._client.get_fund_details(isin)
                raw_asset_type = fund_details.get("assetType")
                if raw_asset_type == "VARIABLE_INCOME":
                    asset_type = AssetType.EQUITY
                elif raw_asset_type == "FIXED_INCOME":
                    asset_type = AssetType.FIXED_INCOME
                elif raw_asset_type == "MONEY_MARKET":
                    asset_type = AssetType.MONEY_MARKET
                elif raw_asset_type == "MIXED":
                    asset_type = AssetType.MIXED
                else:
                    asset_type = AssetType.OTHER

                key_info_sheet = fund_details.get("urlKiid")
                added_values = self._client.get_fund_added_values(
                    security_account_id, isin
                )
                initial_investment = (
                    added_values.get("investmentAddedValue")
                    or fund["initialInvestment"]
                )
                initial_investment = round(Dezimal(initial_investment), 4)

                fund_list.append(
                    FundDetail(
                        id=uuid4(),
                        name=fund["investmentName"],
                        isin=isin,
                        market=fund["marketCode"],
                        shares=Dezimal(fund["shares"]),
                        initial_investment=initial_investment,
                        average_buy_price=round(
                            Dezimal(fund["initialInvestment"])
                            / Dezimal(fund["shares"]),
                            4,
                        ),  # averageCost
                        market_value=round(Dezimal(fund["marketValue"]), 4),
                        type=FundType.MUTUAL_FUND,
                        asset_type=asset_type,
                        currency="EUR",  # Values are in EUR, anyway "liquidationValueCurrency" has fund currency
                        info_sheet_url=key_info_sheet,
                        portfolio=FundPortfolio(id=portfolio_id)
                        if portfolio_id
                        else None,
                    )
                )

        return FundInvestments(fund_list)
