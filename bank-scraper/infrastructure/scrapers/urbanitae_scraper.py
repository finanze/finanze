from datetime import datetime

from dateutil.tz import tzlocal

from application.ports.bank_scraper import BankScraper
from domain.bank import Bank
from domain.bank_data import Investments, BankGlobalPosition, RealStateCFInvestments, RealStateCFDetail
from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.transactions import Transactions, RealStateCFTx, TxType, TxProductType
from infrastructure.scrapers.urbanitae_client import UrbanitaeAPIClient

FUNDED_STATES = ["FUNDED", "POST_PREFUNDING", "FORMALIZED"]
CANCELLED_STATES = ["CLOSED", "CANCELED", "CANCELED_WITH_COMPENSATION"]


class UrbanitaeScraper(BankScraper):
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def __init__(self):
        self.__client = UrbanitaeAPIClient()

    def login(self, credentials: tuple, **kwargs):
        username, password = credentials
        self.__client.login(username, password)

    async def global_position(self) -> BankGlobalPosition:
        wallet = self.__client.get_wallet()
        balance = wallet["balance"]

        investments_data = self.__client.get_investments()

        def map_investment(inv):
            project_details = self.__client.get_project_detail(inv["projectId"])

            months = project_details["details"]["investmentPeriod"]

            return RealStateCFDetail(
                name=inv["projectName"],
                amount=round(inv["investedQuantityActive"], 2),
                interestRate=round(inv["totalNetProfitability"], 2),
                lastInvestDate=datetime.strptime(inv["lastInvestDate"], self.DATETIME_FORMAT),
                months=months,
                type=inv["projectType"],
                businessType=inv["projectBusinessModel"],
                state=inv["projectPhase"],
            )

        real_state_cf_inv_details = [
            map_investment(inv)
            for inv in investments_data if inv["projectPhase"] in FUNDED_STATES
        ]

        total_invested = round(sum([inv.amount for inv in real_state_cf_inv_details]), 2)
        weighted_interest_rate = round(
            (sum([inv.amount * inv.interestRate for inv in real_state_cf_inv_details])
             / sum([inv.amount for inv in real_state_cf_inv_details])) / 100,
            2,
        )
        investments = Investments(
            realStateCF=RealStateCFInvestments(
                invested=total_invested,
                wallet=round(balance, 2),
                weightedInterestRate=weighted_interest_rate,
                details=real_state_cf_inv_details
            )
        )

        return BankGlobalPosition(
            date=datetime.now(tzlocal()),
            investments=investments
        )

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        raw_txs = self.__client.get_transactions()

        def map_tx(tx):
            tx_type_raw = tx["type"]
            tx_type = TxType.INVESTMENT if tx_type_raw == "INVESTMENT" else None
            if not tx_type:
                print(f"Skipping tx {tx['name']} with type {tx_type_raw}")
                return None

            currency = tx["externalProviderData"]["currency"]
            name = tx["externalProviderData"]["argumentValue"]

            return RealStateCFTx(
                id=tx["id"],
                name=name,
                amount=round(tx["amount"], 2),
                currency=currency,
                currencySymbol=CURRENCY_SYMBOL_MAP.get(currency, currency),
                type=tx_type,
                date=datetime.strptime(tx["timestamp"], self.DATETIME_FORMAT),
                source=Bank.URBANITAE,
                productType=TxProductType.REAL_STATE_CF,
                fees=round(tx["fee"], 2),
                retentions=0,
                interests=0,
            )

        txs = [map_tx(tx) for tx in raw_txs if tx["id"] not in registered_txs and tx["type"] == "INVESTMENT"]

        return Transactions(investment=txs)
