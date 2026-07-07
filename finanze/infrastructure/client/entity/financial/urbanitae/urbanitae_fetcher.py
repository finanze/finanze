import logging
from datetime import datetime
from typing import Optional
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
        return await self._client.login(
            username, password, keychain=login_params.keychain
        )

    async def global_position(self) -> GlobalPosition:
        wallet = await self._client.get_wallet()
        balance = Dezimal(wallet["balance"])

        account = Account(
            id=uuid4(),
            total=round(balance, 2),
            currency="EUR",
            type=AccountType.VIRTUAL_WALLET,
        )

        investments_data = await self._client.get_investments()

        real_estate_cf_inv_details = []
        for inv in investments_data:
            if inv["projectPhase"] in ACTIVE_PHASES:
                mapped_inv = await self._map_investment(inv)
                if mapped_inv:
                    real_estate_cf_inv_details.append(mapped_inv)

        products = {
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(
                real_estate_cf_inv_details
            ),
        }

        return GlobalPosition(id=uuid4(), entity=URBANITAE, products=products)

    async def _map_investment(self, inv) -> RealEstateCFDetail | None:
        project_id = inv.get("projectId")
        project_details = await self._client.get_project_detail(project_id)
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
            if "PERCENTAGE" in field_unit and (
                "anual" in field_name or "tipo de interés" in field_name
            ):
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

        elif state == "CLOSED":
            state = "COMPLETED"

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
            fetched_txs = await self._client.get_transactions(page=page, limit=1000)
            raw_txs += fetched_txs

            if len(fetched_txs) < 1000:
                break
            page += 1

        investments_by_name = await self._investments_by_name()

        txs = []
        for tx in raw_txs:
            ref = tx["id"]

            tx_status = tx.get("status")
            if tx_status != "COMPLETED":
                self._log.debug(f"Skipping tx {ref} with status {tx_status}")
                continue

            tx_type_raw = tx.get("type")
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
            fee = round(Dezimal(tx["fee"]), 2)
            tx_date = datetime.strptime(tx["timestamp"], self.DATETIME_FORMAT)
            net_amount = round(Dezimal(tx["amount"]), 2)

            if tx_type_raw == "RENTS":
                payout_split = self._split_return_payout(
                    net_amount, investments_by_name.get(name)
                )

                if payout_split is None:
                    self._log.warning(
                        f"Could not match RENTS tx {ref} to investment '{name}', "
                        f"skipping it"
                    )
                    continue

                repaid_amount, gross_interest, net_interest = payout_split

                repayment_ref = f"{ref}-REPAYMENT"
                interest_ref = f"{ref}-INTEREST"

                if repayment_ref not in registered_txs:
                    txs.append(
                        RealEstateCFTx(
                            id=uuid4(),
                            ref=repayment_ref,
                            name=name,
                            amount=repaid_amount,
                            currency=currency,
                            type=TxType.REPAYMENT,
                            date=tx_date,
                            entity=URBANITAE,
                            product_type=ProductType.REAL_ESTATE_CF,
                            fees=Dezimal(0),
                            retentions=Dezimal(0),
                            net_amount=repaid_amount,
                            source=DataSource.REAL,
                        )
                    )

                if interest_ref not in registered_txs:
                    txs.append(
                        RealEstateCFTx(
                            id=uuid4(),
                            ref=interest_ref,
                            name=name,
                            amount=gross_interest,
                            currency=currency,
                            type=TxType.INTEREST,
                            date=tx_date,
                            entity=URBANITAE,
                            product_type=ProductType.REAL_ESTATE_CF,
                            fees=fee,
                            retentions=gross_interest - net_interest,
                            net_amount=net_interest,
                            source=DataSource.REAL,
                        )
                    )

                continue

            if ref in registered_txs:
                continue

            amount = net_amount
            retentions = Dezimal(0)

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
                    date=tx_date,
                    entity=URBANITAE,
                    product_type=ProductType.REAL_ESTATE_CF,
                    fees=fee,
                    retentions=retentions,
                    net_amount=net_amount,
                    source=DataSource.REAL,
                )
            )

        return Transactions(investment=txs)

    async def _investments_by_name(self) -> dict:
        investments = await self._client.get_investments()
        by_name = {}
        for inv in investments:
            name = inv.get("projectName")
            if name is None:
                continue
            by_name[name] = inv
        return by_name

    def _split_return_payout(
        self, net_amount: Dezimal, inv: Optional[dict]
    ) -> Optional[tuple]:
        if not inv:
            return None

        invested_raw = inv.get("investedQuantity")
        returned_raw = inv.get("returnQuantity")
        if invested_raw is None or returned_raw is None:
            return None

        invested = round(Dezimal(invested_raw), 2)
        returned = round(Dezimal(returned_raw), 2)

        gross_interest_total = round(returned - invested, 2)
        if gross_interest_total <= 0:
            return None

        net_interest_total = round(
            gross_interest_total * (1 - CAPITAL_GAINS_BASE_TAX), 2
        )
        total_net_expected = invested + net_interest_total
        if total_net_expected <= 0:
            return None

        share = net_amount / total_net_expected
        if share <= 0 or share > Dezimal("1.02"):
            return None

        repaid = round(invested * share, 2)
        gross_interest = round(gross_interest_total * share, 2)
        net_interest = round(net_amount - repaid, 2)

        return repaid, gross_interest, net_interest

    async def historical_position(self) -> HistoricalPosition:
        investments_data = await self._client.get_investments()

        real_estate_cf_inv_details = []
        for investment in investments_data:
            mapped_inv = await self._map_investment(investment)
            if mapped_inv:
                real_estate_cf_inv_details.append(mapped_inv)

        return HistoricalPosition(
            {
                ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(
                    real_estate_cf_inv_details
                )
            }
        )
