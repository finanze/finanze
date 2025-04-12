import logging
from datetime import datetime
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from application.ports.entity_scraper import EntityScraper
from domain.dezimal import Dezimal
from domain.native_entities import URBANITAE
from domain.global_position import Investments, GlobalPosition, RealStateCFInvestments, RealStateCFDetail, Account, \
    HistoricalPosition, AccountType
from domain.transactions import Transactions, RealStateCFTx, TxType, ProductType
from infrastructure.scrapers.urbanitae.urbanitae_client import UrbanitaeAPIClient

FUNDED_STATES = ["FUNDED", "POST_PREFUNDING", "FORMALIZED"]
CANCELLED_STATES = ["CLOSED", "CANCELED", "CANCELED_WITH_COMPENSATION"]


class UrbanitaeScraper(EntityScraper):
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def __init__(self):
        self._client = UrbanitaeAPIClient()
        self._log = logging.getLogger(__name__)

    async def login(self, credentials: tuple, **kwargs) -> dict:
        username, password = credentials
        return self._client.login(username, password)

    async def global_position(self) -> GlobalPosition:
        wallet = self._client.get_wallet()
        balance = Dezimal(wallet["balance"])

        account = Account(
            id=uuid4(),
            total=round(balance, 2),
            currency='EUR',
            type=AccountType.VIRTUAL_WALLET
        )

        investments_data = self._client.get_investments()

        real_state_cf_inv_details = [
            self._map_investment(inv)
            for inv in investments_data if inv["projectPhase"] in FUNDED_STATES
        ]

        total_invested = round(sum([inv.amount for inv in real_state_cf_inv_details]), 2)
        weighted_interest_rate = round(
            (sum([inv.amount * inv.interest_rate for inv in real_state_cf_inv_details])
             / sum([inv.amount for inv in real_state_cf_inv_details])),
            4,
        )
        investments = Investments(
            real_state_cf=RealStateCFInvestments(
                total=total_invested,
                weighted_interest_rate=weighted_interest_rate,
                details=real_state_cf_inv_details
            )
        )

        return GlobalPosition(
            id=uuid4(),
            entity=URBANITAE,
            account=[account],
            investments=investments
        )

    def _map_investment(self, inv):
        project_details = self._client.get_project_detail(inv["projectId"])

        months = int(project_details["details"]["investmentPeriod"])
        interest_rate = Dezimal(project_details["fund"]["apreciationProfitability"])
        last_invest_date = datetime.strptime(inv["lastInvestDate"], self.DATETIME_FORMAT)

        return RealStateCFDetail(
            id=uuid4(),
            name=inv["projectName"],
            amount=round(Dezimal(inv["investedQuantityActive"]), 2),
            currency="EUR",
            interest_rate=round(interest_rate / 100, 4),
            last_invest_date=last_invest_date,
            maturity=(last_invest_date + relativedelta(months=months)).date(),
            extended_maturity=None,
            type=inv["projectType"],
            business_type=inv["projectBusinessModel"],
            state=inv["projectPhase"],
        )

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        raw_txs = []
        page = 0
        while True:
            fetched_txs = self._client.get_transactions(page=page, limit=1000)
            raw_txs += fetched_txs

            if len(fetched_txs) < 1000:
                break
            page += 1

        txs = []
        for tx in raw_txs:
            ref = tx["id"]
            if ref in registered_txs:
                continue

            tx_type_raw = tx["type"]
            tx_type = TxType.INVESTMENT if tx_type_raw == "INVESTMENT" else None
            if tx_type != TxType.INVESTMENT:
                self._log.debug(f"Skipping tx {ref} with type {tx_type_raw}")
                continue

            currency = tx["externalProviderData"]["currency"]
            name = tx["externalProviderData"]["argumentValue"]

            txs.append(RealStateCFTx(
                id=uuid4(),
                ref=tx["id"],
                name=name,
                amount=Dezimal(round(tx["amount"], 2)),
                currency=currency,
                type=tx_type,
                date=datetime.strptime(tx["timestamp"], self.DATETIME_FORMAT),
                entity=URBANITAE,
                product_type=ProductType.REAL_STATE_CF,
                fees=round(Dezimal(tx["fee"]), 2),
                retentions=Dezimal(0),
                interests=Dezimal(0),
                net_amount=Dezimal(0),
                is_real=True
            ))

        return Transactions(investment=txs)

    async def historical_position(self) -> HistoricalPosition:
        investments_data = self._client.get_investments()

        real_state_cf_inv_details = [
            self._map_investment(inv)
            for inv in investments_data
        ]

        return HistoricalPosition(
            investments=Investments(
                real_state_cf=RealStateCFInvestments(
                    total=None,
                    weighted_interest_rate=None,
                    details=real_state_cf_inv_details
                )
            )
        )
