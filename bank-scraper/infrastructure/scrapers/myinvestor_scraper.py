from datetime import date, datetime, timezone
from itertools import chain

from application.ports.bank_scraper import BankScraper
from domain.auto_contributions import PeriodicContribution, ContributionFrequency, AutoContributions
from domain.bank_data import Account, AccountAdditionalData, Cards, Card, StockDetail, StockInvestments, FundDetail, \
    FundInvestments, SegoDetail, SegoInvestments, Investments, BankGlobalPosition, BankAdditionalData, Deposit, Deposits
from domain.currency_symbols import CURRENCY_SYMBOL_MAP, SYMBOL_CURRENCY_MAP
from domain.scrap_result import ScrapResultCode, ScrapResult
from domain.scraped_bank_data import ScrapedBankData
from infrastructure.scrapers.myinvestor_client import MyInvestorAPIClient

OLD_DATE_FORMAT = "%d/%m/%Y"


class MyInvestorSummaryGenerator(BankScraper):

    def __init__(self):
        self.__client = MyInvestorAPIClient()

    def login(self, credentials: tuple, params: dict = None):
        username, password = credentials
        self.__client.login(username, password)

    async def generate(self) -> ScrapResult:
        maintenance = self.__client.check_maintenance()

        account_id, securities_account_id, account_data = self.scrape_account()

        cards_data = self.scrape_cards(account_id)

        investments_data = self.scrape_investments(securities_account_id)

        deposits = self.scrape_deposits()

        financial_data = BankGlobalPosition(
            date=datetime.now(timezone.utc),
            account=account_data,
            cards=cards_data,
            deposits=deposits,
            investments=investments_data,
            additionalData=BankAdditionalData(maintenance=maintenance["enMantenimeinto"]),
        )

        try:
            auto_contributions = self.scrape_auto_contributions()
        except Exception as e:
            print(f"Error getting auto contributions: {e}")
            auto_contributions = None

        data = ScrapedBankData(
            position=financial_data,
            autoContributions=auto_contributions
        )

        return ScrapResult(ScrapResultCode.COMPLETED, data)

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
            credit=Card(limit=credit_card_tx["limit"], used=credit_card_tx["consumedMonth"]),
            debit=Card(limit=debit_card_tx["limit"], used=debit_card_tx["consumedMonth"]),
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

        raw_sego_investments = self.__client.get_active_sego_investments()
        total_sego_amount = sum(
            [investment["amount"] for investment in raw_sego_investments]
        )
        weighted_sego_net_interest_rate = round(
            (
                    sum(
                        [
                            investment["amount"] * investment["netInterestRate"]
                            for investment in raw_sego_investments
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
                maturity=(
                    date.fromisoformat(investment["returnDate"][:10]).isoformat()
                    if investment["returnDate"]
                    else None
                ),
                type=investment["operationType"],
            )
            for investment in raw_sego_investments
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

        periodic_contributions = [
            PeriodicContribution(
                alias=auto_contribution["alias"],
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
