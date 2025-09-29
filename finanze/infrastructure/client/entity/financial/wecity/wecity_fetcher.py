import logging
from datetime import date, datetime
from hashlib import sha1
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
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
from domain.native_entities import WECITY
from domain.transactions import RealEstateCFTx, Transactions, TxType
from infrastructure.client.entity.financial.wecity.wecity_client import WecityAPIClient

DATE_FORMAT = "%Y-%m-%d"

INTEREST_SUBCATEGORIES = [
    "intereses ordinarios",
    "intereses de demora",
    "penalización amortización anticipada",
]


def _is_interest(subtype: str) -> bool:
    return any(sub in subtype for sub in INTEREST_SUBCATEGORIES)


def _normalize_transactions(raw_txs: list):
    txs = []
    for tx in raw_txs:
        txs.append(
            {
                "date": datetime.fromtimestamp(tx["date"]),
                "category": tx["type"],
                "sub_category": tx["label"],
                "name": tx["title"].strip(),
                "amount": round(abs(Dezimal(tx["amount"])), 2),
            }
        )

    return sorted(txs, key=lambda txx: (txx["date"], txx["amount"]))


class WecityFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = WecityAPIClient()
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
            session=login_params.session,
        )

    async def global_position(self) -> GlobalPosition:
        wallet = Dezimal(self._client.get_wallet()["LW"]["balance"]) / 100
        account = Account(
            id=uuid4(),
            total=round(wallet, 2),
            currency="EUR",
            type=AccountType.VIRTUAL_WALLET,
        )

        investments = self._client.get_investments()

        investment_details = []
        for inv_id, inv in investments.items():
            pending_amount = Dezimal(inv["amount"]["current"])
            if (
                inv["opportunity"]["state_id"] == 5 and pending_amount == 0
            ):  # It can be marked as completed (5), but there could be pending principal
                continue

            raw_related_txs = self._client.get_investment_transactions(inv_id)[
                "movements"
            ]
            related_txs = _normalize_transactions(raw_related_txs)
            investment_details.append(self._map_investment(related_txs, inv_id, inv))

        products = {
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(investment_details),
        }

        return GlobalPosition(id=uuid4(), entity=WECITY, products=products)

    def _map_investment(self, related_txs, inv_id, inv):
        opportunity = inv["opportunity"]
        name = opportunity["name"].strip()
        amount = Dezimal(inv["amount"]["initial"])
        pending = Dezimal(inv["amount"]["current"])
        investments_details = self._client.get_investment_details(inv_id)
        opportunity = investments_details["opportunity"]

        raw_business_type = opportunity["investment_type_id"]
        business_type = raw_business_type
        if raw_business_type == 1:
            business_type = "EQUITY"
        elif raw_business_type == 2:
            business_type = "LENDING"
        elif raw_business_type == 3:
            business_type = "DONATION"

        raw_project_type = investments_details["opportunity"]["property_type"]["es"]
        project_type = raw_project_type
        if raw_project_type == "Residencial":
            project_type = "HOUSING"
        elif raw_project_type == "Suelo":
            project_type = "FLOOR"
        elif raw_project_type == "Oficinas":
            project_type = "COMMERCIAL_OFFICE"
        elif raw_project_type == "Hotelero":
            project_type = "HOTEL"
        elif raw_project_type == "Local":
            project_type = "PREMISES"
        elif raw_project_type == "Loft":
            project_type = "LOFT"
        elif raw_project_type == "Renovables":
            project_type = "RENEWABLES"
        elif raw_project_type == "Hospital":
            project_type = "HOSPITAL"
        elif raw_project_type == "Logístico":
            project_type = "LOGISTIC"

        state_id = opportunity["state_id"]
        state = "-"
        if state_id == 2:
            state = "UNDER_REVIEW"
        elif (
            state_id == 1 or state_id == 3 or state_id == 12
        ):  # 1 = "Abierta", 3 = "Financiada", 12 = "?"
            state = "IN_PROGRESS"
        elif state_id == 5:
            state = "COMPLETED"

        last_invest_date = max(
            [tx["date"] for tx in related_txs if "investment" == tx["category"]],
            default=None,
        )

        last_invest_date = last_invest_date.replace(tzinfo=tzlocal())

        periods = inv["periods"]
        ordinary_period = periods["ordinary"]
        start_date = last_invest_date.date()

        if not start_date:
            original_start_date = opportunity.get("date_start")
            if original_start_date:
                start_date = (
                    datetime.fromtimestamp(original_start_date)
                    .replace(tzinfo=tzlocal())
                    .date()
                )

        if ordinary_period:
            start_date_field = ordinary_period.get("fecha_inicio")
            if start_date_field:
                start_date = datetime.strptime(start_date_field, DATE_FORMAT).date()

        extended_period = periods.get("prorroga", None)
        if extended_period:
            extended_period = extended_period["plazo"]

        maturity = start_date + relativedelta(months=int(ordinary_period["plazo"]))
        extended_maturity = (
            (maturity + relativedelta(months=int(extended_period)))
            if extended_period
            else None
        )

        return RealEstateCFDetail(
            id=uuid4(),
            name=name,
            amount=round(amount, 2),
            pending_amount=round(pending, 2),
            currency="EUR",
            interest_rate=round(Dezimal(opportunity["annual_profitability"]) / 100, 4),
            profitability=round(Dezimal(opportunity["total_profitability"]) / 100, 4),
            last_invest_date=last_invest_date,
            maturity=maturity,
            extended_maturity=extended_maturity,
            type=project_type,
            business_type=business_type,
            state=state,
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        raw_transactions = _normalize_transactions(self._client.get_transactions())

        txs = []
        for tx in raw_transactions:
            tx_type_raw = tx["category"].lower()
            tx_subtype_raw = tx["sub_category"].lower()

            if tx_type_raw == "investment":
                tx_type = TxType.INVESTMENT
            elif tx_type_raw == "moneyback":
                if tx_subtype_raw == "devolución de capital":
                    tx_type = TxType.REPAYMENT
                elif tx_subtype_raw == "reparto de dividendos":
                    tx_type = TxType.DIVIDEND
                elif _is_interest(tx_subtype_raw):
                    tx_type = TxType.INTEREST
                else:
                    self._log.debug(
                        f"Skipping tx {tx['name']} with subtype {tx_subtype_raw}"
                    )
                    continue
            else:
                self._log.debug(f"Skipping tx {tx['name']} with type {tx_type_raw}")
                continue

            name = tx["name"]
            amount = round(Dezimal(tx["amount"]), 2)
            tx_date = tx["date"].replace(tzinfo=tzlocal())

            ref = self._calc_tx_id(name, tx_date, amount, tx_type)

            if ref in registered_txs:
                continue

            interests = Dezimal(0)
            retentions = Dezimal(0)
            net_amount = amount
            # We assume there are retentions
            if tx_type == TxType.INTEREST or tx_type == TxType.DIVIDEND:
                amount = net_amount / (1 - CAPITAL_GAINS_BASE_TAX)
                retentions = amount - net_amount

            if tx_type == TxType.INTEREST:
                interests = amount

            txs.append(
                RealEstateCFTx(
                    id=uuid4(),
                    ref=ref,
                    name=name,
                    amount=round(amount, 2),
                    currency="EUR",
                    type=tx_type,
                    date=tx_date,
                    entity=WECITY,
                    product_type=ProductType.REAL_ESTATE_CF,
                    fees=Dezimal(0),
                    retentions=round(retentions, 2),
                    interests=round(interests, 2),
                    net_amount=round(net_amount, 2),
                    source=DataSource.REAL,
                )
            )

        return Transactions(investment=txs)

    @staticmethod
    def _calc_tx_id(
        inv_name: str, tx_date: date, amount: Dezimal, tx_type: TxType
    ) -> str:
        return sha1(
            f"W_{inv_name}_{tx_date.isoformat()}_{amount}_{tx_type}".encode("UTF-8")
        ).hexdigest()

    async def historical_position(self) -> HistoricalPosition:
        investments = self._client.get_investments()

        investment_details = []
        for inv_id, inv in investments.items():
            raw_related_txs = self._client.get_investment_transactions(inv_id)[
                "movements"
            ]
            related_txs = _normalize_transactions(raw_related_txs)
            investment_details.append(self._map_investment(related_txs, inv_id, inv))

        return HistoricalPosition(
            {ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(investment_details)}
        )
