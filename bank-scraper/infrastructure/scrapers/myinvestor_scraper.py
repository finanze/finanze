from datetime import date, datetime
from hashlib import sha1
from typing import Optional

from dateutil.tz import tzlocal
from itertools import chain

from application.ports.bank_scraper import BankScraper
from domain.auto_contributions import PeriodicContribution, ContributionFrequency, AutoContributions
from domain.bank import Bank
from domain.bank_data import Account, AccountAdditionalData, Cards, Card, StockDetail, StockInvestments, FundDetail, \
    FundInvestments, SegoDetail, SegoInvestments, Investments, BankGlobalPosition, BankAdditionalData, Deposit, Deposits
from domain.currency_symbols import CURRENCY_SYMBOL_MAP, SYMBOL_CURRENCY_MAP
from domain.transactions import Transactions, FundTx, TxType, StockTx, TxProductType, SegoTx
from infrastructure.scrapers.myinvestor_client import MyInvestorAPIClient

OLD_DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M:%S"
OLD_DATE_TIME_FORMAT = OLD_DATE_FORMAT + " " + TIME_FORMAT
DASH_OLD_DATE_TIME_FORMAT = "%Y-%m-%d " + TIME_FORMAT

ISO8601_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

ACTIVE_SEGO_STATES = ["DISPUTE", "MANAGING_COLLECTION", "NOT_ARRIVING_COLLECTION_DATE"]
FINISHED_SEGO_STATES = ["CASHED", "FAILED"]


class MyInvestorSummaryGenerator(BankScraper):

    def __init__(self):
        self.__client = MyInvestorAPIClient()

    def login(self, credentials: tuple, **kwargs):
        username, password = credentials
        self.__client.login(username, password)

    async def global_position(self) -> BankGlobalPosition:
        maintenance = self.__client.check_maintenance()

        account_id, securities_account_id, account_data = self.scrape_account()

        cards_data = self.scrape_cards(account_id)

        investments_data = self.scrape_investments(securities_account_id)

        deposits = self.scrape_deposits()

        return BankGlobalPosition(
            date=datetime.now(tzlocal()),
            account=account_data,
            cards=cards_data,
            deposits=deposits,
            investments=investments_data,
            additionalData=BankAdditionalData(maintenance=maintenance["enMantenimeinto"]),
        )

    async def auto_contributions(self) -> AutoContributions:
        return self.scrape_auto_contributions()

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        accounts = self.__client.get_accounts()
        securities_account_id = accounts[0]["idCuentaValores"]

        fund_txs = self.scrape_fund_txs(securities_account_id, registered_txs)
        stock_txs = self.scrape_stock_txs(securities_account_id, registered_txs)

        sego_txs = self.scrape_sego_txs(registered_txs)

        investment_txs = fund_txs + stock_txs + sego_txs

        return Transactions(investment=investment_txs)

    def scrape_account(self):
        accounts = self.__client.get_accounts()

        account_id = accounts[0]["idCuenta"]
        securities_account_id = accounts[0]["idCuentaValores"]

        current_interest_rate = None
        avg_interest_rate = None
        remuneration_type = None

        try:
            remuneration_details = self.__client.get_account_remuneration(account_id)
            current_interest_rate = round(remuneration_details["taePromocion"] / 100, 4)
            avg_interest_rate = round(
                remuneration_details["taeMediaCalculada"] / 100, 4
            )
            remuneration_type = remuneration_details["tipo"]
        except Exception as e:
            print(f"Error getting account remuneration: {e}")

        return account_id, securities_account_id, Account(
            total=accounts[0]["importeCuenta"],
            retained=accounts[0]["retencionesSaldoCuenta"],
            interest=current_interest_rate,
            additionalData=AccountAdditionalData(
                averageInterestRate=avg_interest_rate,
                remunerationType=remuneration_type,
            ),
        )

    def scrape_cards(self, account_id: str):
        cards = self.__client.get_cards(account_id=account_id)
        credit_card = next(
            (card for card in cards if card["cardType"] == "CREDIT"), None
        )
        debit_card = next((card for card in cards if card["cardType"] == "DEBIT"), None)

        credit_card_tx = self.__client.get_card_transactions(credit_card["cardId"])
        debit_card_tx = self.__client.get_card_transactions(debit_card["cardId"])

        return Cards(
            credit=Card(limit=credit_card_tx["limit"], used=abs(credit_card_tx["consumedMonth"])),
            debit=Card(limit=debit_card_tx["limit"], used=abs(debit_card_tx["consumedMonth"])),
        )

    def scrape_deposits(self):
        deposits_raw = self.__client.get_deposits()

        deposit_list = [
            Deposit(
                name=deposit["depositName"],
                amount=round(deposit["amount"], 2),
                totalInterests=round(deposit["grossInterest"], 2),
                interestRate=round(deposit["tae"] / 100, 2),
                maturity=datetime.strptime(deposit["expirationDate"], "%Y-%m-%dT%H:%M:%S.%fZ").date(),
                creation=datetime.strptime(deposit["creationDate"], "%Y-%m-%dT%H:%M:%S.%fZ").date(),
            )
            for deposit in deposits_raw
        ]

        return Deposits(
            total=sum([deposit["amount"] for deposit in deposits_raw]),
            totalInterests=sum([deposit["grossInterest"] for deposit in deposits_raw]),
            weightedInterestRate=round(
                (sum([deposit["amount"] * deposit["tae"] for deposit in deposits_raw])
                 / sum([deposit["amount"] for deposit in deposits_raw])) / 100,
                2,
            ),
            details=deposit_list,
        )

    def scrape_investments(self, securities_account_id: str):
        stocks_account = None
        for account in self.__client.get_stocks_summary():
            if account["idCuenta"] == securities_account_id:
                stocks_account = account
                break

        stock_list = []
        if stocks_account:
            stock_list = [
                StockDetail(
                    name=stock["nombre"],
                    ticker=stock["ticker"],
                    isin=stock["isin"],
                    market=stock["codigoMercado"],
                    shares=stock["titulos"],
                    initialInvestment=round(stock["inversionInicial"], 4),
                    averageBuyPrice=round(stock["inversionInicial"] / stock["titulos"], 4),
                    marketValue=round(stock["valorMercado"], 4),
                    currency=stock["divisa"],
                    currencySymbol=CURRENCY_SYMBOL_MAP.get(stock["divisa"], stock["divisa"]),
                    type=stock["tipoProductoBrokerEnum"],
                    subtype=stock.get("codigoTipoActivo"),
                )
                for stock in stocks_account["accionesEtfDtoList"]
            ]

        stock_data = StockInvestments(
            initialInvestment=round(stocks_account["inversionInicial"], 4) if stocks_account else 0,
            marketValue=round(stocks_account["valorMercado"], 4) if stocks_account else 0,
            details=stock_list,
        )

        funds_account = None
        for account in self.__client.get_funds_and_portfolios_summary():
            if (
                    account["idCuenta"] == securities_account_id
                    and account["tipoCuentaEnum"] == "VALORES"
            ):
                funds_account = account
                break

        fund_list = []
        if funds_account:
            all_account_funds = map(
                lambda cat: cat["inversionesDtoList"],
                funds_account["inversionesCuentaValores"].values(),
            )
            raw_fund_list = list(chain(*list(all_account_funds)))
            fund_list = [
                FundDetail(
                    name=fund["nombreInversion"],
                    isin=fund["isin"],
                    market=fund["codigoMercado"],
                    shares=fund["participaciones"],
                    initialInvestment=round(fund["inversionInicial"], 4),
                    averageBuyPrice=round(fund["inversionInicial"] / fund["participaciones"], 4),
                    marketValue=round(fund["valorMercado"], 4),
                    currency=SYMBOL_CURRENCY_MAP.get(
                        fund["divisaValorLiquidativo"], fund["divisaValorLiquidativo"]
                    ),
                    currencySymbol=fund["divisaValorLiquidativo"],
                    lastUpdate=datetime.strptime(fund["fechaCotizacion"], OLD_DATE_FORMAT).date(),
                )
                for fund in raw_fund_list
            ]

        fund_data = FundInvestments(
            initialInvestment=round(funds_account["totalInvertido"], 4) if funds_account else 0,
            marketValue=round(funds_account["valorMercado"], 4) if funds_account else 0,
            details=fund_list,
        )

        raw_sego_summary = self.__client.get_sego_global_position()
        raw_sego_movements = self.__client.get_sego_movements()
        sego_investment_movements = sorted(
            [
                movement
                for movement in raw_sego_movements
                if movement["type"] == "TRANSFER"
                   and movement["amount"] < 0
                   and "Inversión" in movement["description"]
            ],
            key=lambda movement: movement["date"],
        )
        raw_sego_investments = self.__client.get_all_sego_investments()
        active_sego_investments = [
            investment for investment in raw_sego_investments if investment["operationStateType"] in ACTIVE_SEGO_STATES
        ]
        total_sego_amount = sum(
            [investment["amount"] for investment in active_sego_investments]
        )
        weighted_sego_net_interest_rate = round(
            (
                    sum(
                        [
                            investment["amount"] * investment["netInterestRate"]
                            for investment in active_sego_investments
                        ]
                    )
                    / total_sego_amount
            )
            / 100,
            4,
        )

        sego_investments = [
            SegoDetail(
                name=investment["operationName"],
                amount=investment["amount"],
                interestRate=round(investment["netInterestRate"] / 100, 4),
                start=date.fromisoformat(
                    next(
                        (
                            movement["date"][0:10]
                            for movement in sego_investment_movements
                            if investment["operationName"] in movement["description"]
                        ),
                        None,
                    )
                ),
                maturity=(
                    date.fromisoformat(investment["returnDate"][:10])
                    if investment["returnDate"]
                    else None
                ),
                type=investment["operationType"],
                state=investment["operationStateType"]
            )
            for investment in active_sego_investments
        ]

        sego_data = SegoInvestments(
            invested=raw_sego_summary["inverted"],
            wallet=raw_sego_summary["available"],
            weightedInterestRate=weighted_sego_net_interest_rate,
            details=sego_investments,
        )

        return Investments(
            stocks=stock_data,
            funds=fund_data,
            sego=sego_data,
        )

    def scrape_auto_contributions(self) -> AutoContributions:
        auto_contributions = self.__client.get_auto_contributions()

        def get_frequency(frequency) -> ContributionFrequency:
            return {
                "UNA_SEMANA": ContributionFrequency.WEEKLY,
                "DOS_SEMANAS": ContributionFrequency.BIWEEKLY,
                "UN_MES": ContributionFrequency.MONTHLY,
                "DOS_MESES": ContributionFrequency.BIMONTHLY,
                "TRES_MESES": ContributionFrequency.QUARTERLY,
                "SEIS_MESES": ContributionFrequency.SEMIANNUAL,
                "UN_ANYO": ContributionFrequency.YEARLY,
            }[frequency]

        def get_date(date_str):
            if not date_str:
                return None
            return datetime.strptime(date_str, OLD_DATE_FORMAT).date()

        def get_alias(auto_contribution):
            alias = auto_contribution["alias"]
            if alias:
                return alias
            fund_name = auto_contribution["nombreFondo"]
            if fund_name:
                return fund_name
            return None

        periodic_contributions = [
            PeriodicContribution(
                alias=get_alias(auto_contribution),
                isin=auto_contribution["codigoIsin"],
                amount=round(auto_contribution["importe"], 2),
                since=get_date(auto_contribution["periodicidadAportacionDto"]["fechaDesde"]),
                until=get_date(auto_contribution["periodicidadAportacionDto"]["fechaHasta"]),
                frequency=get_frequency(auto_contribution["periodicidadAportacionDto"]["periodicidad"]),
                active=auto_contribution["estadoAportacionEnum"] == "ACTIVA",
            )
            for auto_contribution in auto_contributions
        ]

        return AutoContributions(
            periodic=periodic_contributions
        )

    def scrape_fund_txs(self, securities_account_id: str, registered_txs: set[str]) -> list[FundTx]:
        raw_fund_orders = self.__client.get_fund_orders(securities_account_id=securities_account_id,
                                                        from_date=date.fromisocalendar(2020, 1, 1))

        fund_txs = []
        for order in raw_fund_orders:
            ref = order["referencia"]

            if ref in registered_txs:
                continue

            raw_order_details = self.__client.get_fund_order_details(ref)
            order_date = datetime.strptime(raw_order_details["fechaOrden"] + " " + raw_order_details["horaOrden"],
                                           OLD_DATE_TIME_FORMAT)
            execution_op = None
            linked_ops = raw_order_details["operacionesAsociadas"]
            if linked_ops:
                execution_op = linked_ops[0]
            execution_date = datetime.strptime(execution_op["fechaHoraEjecucion"], OLD_DATE_TIME_FORMAT)

            raw_operation_type = order["tipoOperacion"]
            if "SUSCRIP" in raw_operation_type:
                operation_type = TxType.BUY
            elif "REEMBOLSO" in raw_operation_type:
                operation_type = TxType.SELL
            else:
                print(f"Unknown operation type: {raw_operation_type}")
                continue

            fund_txs.append(
                FundTx(
                    id=ref,
                    name=order["nombreFondo"].strip(),
                    amount=round(execution_op["efectivoBruto"], 2),
                    netAmount=round(execution_op["efectivoNeto"], 2),
                    currency=SYMBOL_CURRENCY_MAP.get(order["divisa"], order["divisa"]),
                    currencySymbol=order["divisa"],
                    type=operation_type,
                    orderDate=order_date,
                    source=Bank.MY_INVESTOR,
                    isin=order["codIsin"],
                    shares=round(raw_order_details["titulosEjecutados"], 4),
                    price=round(execution_op["precioBruto"], 4),
                    market=order["mercado"],
                    fees=round(execution_op["comisiones"], 2),
                    retentions=0,
                    date=execution_date,
                    productType=TxProductType.FUND
                )
            )

        return fund_txs

    def scrape_stock_txs(self, securities_account_id: str, registered_txs: set[str]) -> list[StockTx]:
        raw_stock_orders = self.__client.get_stock_orders(securities_account_id=securities_account_id,
                                                          from_date=date.fromisocalendar(2020, 1, 1),
                                                          completed=False)

        stock_txs = []
        for order in raw_stock_orders:
            ref = order["referencia"]

            if ref in registered_txs:
                break

            raw_order_details = self.__client.get_stock_order_details(ref)
            order_date = datetime.strptime(raw_order_details["fechaOrden"], OLD_DATE_TIME_FORMAT)
            linked_ops = raw_order_details["operacionesAsociadas"]
            if not linked_ops:
                print(f"Order {ref} has no linked operations")
                continue
            execution_op = linked_ops[0]
            execution_date = datetime.strptime(execution_op["fechaHoraEjecucion"], DASH_OLD_DATE_TIME_FORMAT)

            raw_operation_type = order["operacion"]
            if "COMPRA" in raw_operation_type:
                operation_type = TxType.BUY
            elif "VENTA" in raw_operation_type:
                operation_type = TxType.SELL
            else:
                print(f"Unknown operation type: {raw_operation_type}")
                continue

            amount = round(execution_op["efectivoBruto"], 2)
            net_amount = round(execution_op["efectivoNeto"], 2)

            fees = 0
            if operation_type == TxType.BUY:
                # Financial Tx Tax not included in "comisionCorretaje", "comisionMiembroMercado" and "costeCanon"
                fees = net_amount - amount
            elif operation_type == TxType.SELL:
                fees = execution_op["comisionCorretaje"] + execution_op["comisionMiembroMercado"] + execution_op[
                    "costeCanon"]

            stock_txs.append(
                StockTx(
                    id=ref,
                    name=order["nombreInstrumento"].strip(),
                    ticker=order["ticker"],
                    amount=amount,
                    netAmount=net_amount,
                    currency=order["divisa"],
                    currencySymbol=CURRENCY_SYMBOL_MAP.get(order["divisa"], order["divisa"]),
                    type=operation_type,
                    orderDate=order_date,
                    source=Bank.MY_INVESTOR,
                    isin=raw_order_details["codIsin"],
                    shares=round(raw_order_details["titulosEjecutados"], 4),
                    price=round(execution_op["precioBruto"], 4),
                    market=order["codMercado"],
                    fees=round(fees, 2),
                    retentions=0,
                    date=execution_date,
                    productType=TxProductType.STOCK_ETF
                )
            )

        return stock_txs

    def scrape_sego_txs(self, registered_txs: set[str]) -> list[SegoTx]:
        all_investments = self.__client.get_all_sego_investments()
        investment_names = [investment["operationName"] for investment in all_investments]

        txs = self.__client.get_sego_movements()

        investment_txs = {}

        for tx in txs:
            if tx["type"] == "TRANSFER":
                matching_investment_name = next(
                    (investment_name for investment_name in investment_names if investment_name in tx["description"]),
                    None
                )
                if matching_investment_name:
                    if matching_investment_name not in investment_txs:
                        investment_txs[matching_investment_name] = {}

                    description = tx["description"].lower()
                    if "comisiones" in description:
                        investment_txs[matching_investment_name]["fee"] = tx
                    elif "retención" in description:
                        investment_txs[matching_investment_name]["tax"] = tx
                    elif "devolución" in description and "intereses" in description:
                        investment_txs[matching_investment_name]["interests"] = tx
                    elif "devolución" in description and "capital" in description:
                        investment_txs[matching_investment_name]["maturity"] = tx
                    elif "inversión" in description:
                        if not investment_txs[matching_investment_name].get("investment", None):
                            investment_txs[matching_investment_name]["investment"] = []

                        investment_txs[matching_investment_name]["investment"].append(tx)
                    else:
                        print(f"Unknown SEGO transaction type: {description}")

        sego_txs = []

        for name, txs in investment_txs.items():
            maturity_tx = txs.get("maturity", None)
            investment_txs = txs.get("investment", [])
            investment_txs = sorted(investment_txs, key=lambda txx: (txx["date"], txx["amount"]))

            repeated_inv_counter = 0
            last_inv = None
            for tx in investment_txs:
                if last_inv and last_inv["date"] == tx["date"] and last_inv["amount"] == tx["amount"]:
                    repeated_inv_counter += 1
                last_inv = tx

                tx_type = TxType.INVESTMENT
                stored_tx = self.map_sego_txs(tx, name, tx_type, repeated_inv_counter, 0, 0, 0, registered_txs)
                if stored_tx:
                    sego_txs.append(stored_tx)

            if maturity_tx:
                interests = 0
                fee = 0
                tax = 0
                interest_tx = txs.get("interests", None)
                if interest_tx:
                    interests = round(interest_tx["amount"], 2)
                    fee_tx = txs["fee"]
                    fee = abs(round(fee_tx["amount"], 2))
                    tax_tx = txs["tax"]
                    tax = abs(round(tax_tx["amount"], 2))

                tx_type = TxType.MATURITY
                stored_tx = self.map_sego_txs(maturity_tx, name, tx_type, 0, fee, tax, interests, registered_txs)
                if stored_tx:
                    sego_txs.append(stored_tx)

        return sego_txs

    def map_sego_txs(self,
                     tx: dict,
                     name: str,
                     tx_type: TxType,
                     repeat_counter: int,
                     fee: float,
                     tax: float,
                     interests: float,
                     registered_txs: set[str]) -> Optional[SegoTx]:
        tx_date = datetime.strptime(tx["date"], ISO8601_DATETIME_FORMAT)
        raw_amount = round(tx["amount"], 2)

        amount = abs(raw_amount) + interests - fee - tax

        calc_id = self.calc_sego_tx_id(name, tx_date, amount, tx_type, repeat_counter)
        if calc_id not in registered_txs:
            currency_symbol = tx["formattedAmount"][-1]
            currency = SYMBOL_CURRENCY_MAP.get(currency_symbol, "EUR")

            return SegoTx(
                id=calc_id,
                name=name,
                amount=amount,
                currency=currency,
                currencySymbol=currency_symbol,
                type=tx_type,
                date=tx_date,
                source=Bank.MY_INVESTOR,
                productType=TxProductType.SEGO,
                fees=fee,
                retentions=tax,
                interests=interests
            )

        return None

    @staticmethod
    def calc_sego_tx_id(inv_name: str,
                        tx_date: datetime,
                        amount: float,
                        tx_type: TxType,
                        repeat_counter: int) -> str:
        return sha1(
            f"S_{inv_name}_{tx_date.isoformat()}_{amount}_{tx_type}_{repeat_counter}".encode("UTF-8")).hexdigest()
