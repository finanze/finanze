import logging
from datetime import datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.relativedelta import relativedelta
from domain.constants import CAPITAL_GAINS_BASE_TAX
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    HistoricalPosition,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)
from domain.native_entities import URBANITAE
from domain.transactions import RealEstateCFTx, Transactions, TxType
from infrastructure.client.entity.financial.urbanitae.urbanitae_client import (
    UrbanitaeAPIClient,
)

FUNDED_PHASES = ["FUNDED", "POST_PREFUNDING", "FORMALIZED"]
RENT_SOLD_PHASES = ["ACQUIRED", "REFORM", "FOR_RENT", "RENTED", "FOR_SALE", "SOLD"]

INITIAL_PHASES = ["IN_STUDY", "POST_STUDY"]
ACTIVE_PHASES = (
    ["PREFUNDING", "POST_PREFUNDING", "FUNDING"] + FUNDED_PHASES + RENT_SOLD_PHASES
)
CANCELLED_PHASES = ["CLOSED", "CANCELED", "CANCELED_WITH_COMPENSATION"]

INVESTMENT_TXS = ["INVESTMENT", "PREFUNDING_INVESTMENT"]
REFUND_TXS = ["INVESTMENT_REFUND", "PREFUNDING_INVESTMENT_REFUND", "INVESTMENT_ERROR"]


class UrbanitaeFetcher(FinancialEntityFetcher):
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

    def __init__(self):
        self._client = UrbanitaeAPIClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        return self._client.login(username, password)

    async def global_position(self) -> GlobalPosition:
        wallet = self._client.get_wallet()
        balance = Dezimal(wallet["balance"])

        account = Account(
            id=uuid4(),
            total=round(balance, 2),
            currency="EUR",
            type=AccountType.VIRTUAL_WALLET,
        )

        investments_data = self._client.get_investments()

        real_estate_cf_inv_details = []
        for inv in investments_data:
            if inv["projectPhase"] in ACTIVE_PHASES:
                mapped_inv = self._map_investment(inv)
                if mapped_inv:
                    real_estate_cf_inv_details.append(mapped_inv)

        products = {
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(
                real_estate_cf_inv_details
            ),
        }

        return GlobalPosition(id=uuid4(), entity=URBANITAE, products=products)

    def _map_investment(self, inv) -> RealEstateCFDetail | None:
        project_id = inv.get("projectId")
        project_details = self._client.get_project_detail(project_id)
        details = project_details.get("details")
        fund_details = project_details.get("fund")
        if not details or not fund_details:
            self._log.warning("No details found for project %s", project_id)
            return None

        months = int(details["investmentPeriod"])
        interest_rate = Dezimal(
            fund_details.get("apreciationProfitability")
            or fund_details.get("totalNetProfitability")
        )

        fields = fund_details.get("fields", [])
        for field in fields:
            field_name = field.get("name", "").lower()
            field_unit = field.get("unit", "").upper()
            if "PERCENTAGE" in field_unit and "anual" in field_name:
                field_percentage = Dezimal(field.get("amount") or 0)
                if field_percentage > 0:
                    interest_rate = (
                        field_percentage
                        if field_percentage < interest_rate
                        else interest_rate
                    )

        last_invest_date = datetime.strptime(
            inv["lastInvestDate"], self.DATETIME_FORMAT
        )

        project_type = inv["projectType"]  # SOLD, LENDING, RENT, RENT_AND_SOLD
        business_model = inv[
            "projectBusinessModel"
        ]  # HOUSING, COMMERCIAL_OFFICE, INDUSTRIAL_UNIT
        state = inv["projectPhase"]
        if state == "FORMALIZED":
            state = "IN_PROGRESS"

        amount = round(Dezimal(inv["investedQuantity"]), 2)
        pending_amount = round(Dezimal(inv["investedQuantityActive"]), 2)

        return RealEstateCFDetail(
            id=uuid4(),
            name=inv["projectName"],
            amount=amount,
            pending_amount=pending_amount,
            currency="EUR",
            interest_rate=round(interest_rate / 100, 4),
            last_invest_date=last_invest_date,
            start=last_invest_date,
            maturity=(last_invest_date + relativedelta(months=months)).date(),
            extended_maturity=None,
            type=project_type,
            business_type=business_model,
            state=state,
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
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
            if tx_type_raw in INVESTMENT_TXS:
                tx_type = TxType.INVESTMENT
            elif tx_type_raw in REFUND_TXS:
                tx_type = (
                    TxType.REPAYMENT
                )  # Unclear if it contains the interest or just repayment
            elif tx_type_raw == "RENTS":
                tx_type = TxType.INTEREST
            elif tx_type_raw == "APPRECIATION":
                tx_type = TxType.INTEREST  # ??
            else:
                self._log.debug(f"Skipping tx {ref} with type {tx_type_raw}")
                continue

            currency = tx["externalProviderData"]["currency"]
            name = tx["externalProviderData"]["argumentValue"]

            amount = round(Dezimal(tx["amount"]), 2)
            fee = round(Dezimal(tx["fee"]), 2)

            retentions = Dezimal(0)
            net_amount = amount

            if tx_type == TxType.INTEREST:
                amount = net_amount / (1 - CAPITAL_GAINS_BASE_TAX)
                retentions = amount - net_amount

            txs.append(
                RealEstateCFTx(
                    id=uuid4(),
                    ref=ref,
                    name=name,
                    amount=amount,
                    currency=currency,
                    type=tx_type,
                    date=datetime.strptime(tx["timestamp"], self.DATETIME_FORMAT),
                    entity=URBANITAE,
                    product_type=ProductType.REAL_ESTATE_CF,
                    fees=fee,
                    retentions=retentions,
                    net_amount=net_amount,
                    source=DataSource.REAL,
                )
            )

        return Transactions(investment=txs)

    async def historical_position(self) -> HistoricalPosition:
        investments_data = self._client.get_investments()

        real_estate_cf_inv_details = []
        for investment in investments_data:
            mapped_inv = self._map_investment(investment)
            if mapped_inv:
                real_estate_cf_inv_details.append(mapped_inv)

        return HistoricalPosition(
            {
                ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(
                    real_estate_cf_inv_details
                )
            }
        )
