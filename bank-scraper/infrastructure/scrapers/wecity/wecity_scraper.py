import logging
from datetime import datetime, date
from hashlib import sha1
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal

from application.ports.entity_scraper import EntityScraper
from domain.dezimal import Dezimal
from domain.native_entities import WECITY
from domain.global_position import GlobalPosition, RealStateCFDetail, RealStateCFInvestments, Investments, Account, \
    HistoricalPosition, AccountType
from domain.transactions import Transactions, RealStateCFTx, TxType, ProductType
from infrastructure.scrapers.wecity.wecity_client import WecityAPIClient

DATE_FORMAT = "%Y-%m-%d"


class WecityScraper(EntityScraper):

    def __init__(self):
        self._client = WecityAPIClient()
        self._log = logging.getLogger(__name__)

    async def login(self, credentials: tuple, **kwargs) -> dict:
        username, password = credentials
        process_id = kwargs.get("processId", None)
        code = kwargs.get("code", None)
        avoid_new_login = kwargs.get("avoidNewLogin", False)

        return self._client.login(username, password, avoid_new_login, process_id, code)

    async def global_position(self) -> GlobalPosition:
        wallet = Dezimal(self._client.get_wallet()["LW"]["balance"])
        account = Account(
            id=uuid4(),
            total=round(wallet, 2),
            currency='EUR',
            type=AccountType.VIRTUAL_WALLET
        )

        txs = self.scrape_transactions()
        investments = self._client.get_investments()

        investment_details = []
        for inv_id, inv in investments.items():
            investment_details.append(self._map_investment(txs, inv_id, inv))

        total_invested = round(sum([inv.amount for inv in investment_details]), 2)
        weighted_interest_rate = round(
            (sum([inv.amount * inv.interest_rate for inv in investment_details])
             / sum([inv.amount for inv in investment_details])),
            4,
        )
        investments = Investments(
            real_state_cf=RealStateCFInvestments(
                total=total_invested,
                weighted_interest_rate=weighted_interest_rate,
                details=investment_details
            )
        )

        return GlobalPosition(
            id=uuid4(),
            entity=WECITY,
            account=[account],
            investments=investments
        )

    def _map_investment(self, txs, inv_id, inv):
        opportunity = inv["opportunity"]
        name = opportunity["name"].strip()
        amount = Dezimal(inv["amount"]["current"])
        investments_details = self._client.get_investment_details(inv_id)

        raw_business_type = opportunity["investment_type_id"]
        business_type = raw_business_type
        if raw_business_type == 2:
            business_type = "LENDING"

        raw_project_type = investments_details["opportunity"]["property_type"]["es"]
        project_type = raw_project_type
        if raw_project_type == "Residencial":
            project_type = "HOUSING"
        elif raw_project_type == "Suelo":
            project_type = "FLOOR"

        state_id = opportunity["state_id"]
        state = "-"
        if state_id == 3:
            state = "FUNDED"

        last_invest_date = max(
            [tx["date"] for tx in txs if "investment" == tx["category"] and tx["name"] == name],
            default=None)

        last_invest_date = last_invest_date.replace(tzinfo=tzlocal())

        periods = inv["periods"]
        ordinary_period = periods["ordinary"]
        start_date = last_invest_date
        if ordinary_period:
            start_date = ordinary_period.get("fecha_inicio", None)
            if start_date:
                start_date = datetime.strptime(start_date, DATE_FORMAT).date()

        extended_period = periods.get("prorroga", None)
        if extended_period:
            extended_period = extended_period["plazo"]

        maturity = start_date + relativedelta(months=int(ordinary_period["plazo"]))
        extended_maturity = (maturity + relativedelta(months=int(extended_period))) if extended_period else None

        return RealStateCFDetail(
            id=uuid4(),
            name=name,
            amount=round(amount, 2),
            currency="EUR",
            interest_rate=round(Dezimal(opportunity["annual_profitability"]) / 100, 4),
            last_invest_date=last_invest_date,
            maturity=maturity,
            extended_maturity=extended_maturity,
            type=project_type,
            business_type=business_type,
            state=state,
        )

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        raw_transactions = self.scrape_transactions()

        txs = []
        for tx in raw_transactions:
            tx_type_raw = tx["category"]
            if tx_type_raw not in ["investment"]:
                continue
            tx_type = TxType.INVESTMENT if "investment" == tx_type_raw else None
            if not tx_type:
                self._log.debug(f"Skipping tx {tx['name']} with type {tx_type_raw}")
                continue

            name = tx["name"]
            amount = round(Dezimal(tx["amount"]), 2)
            tx_date = tx["date"].replace(tzinfo=tzlocal())

            ref = self._calc_tx_id(name, tx_date, amount, tx_type)

            if ref in registered_txs:
                continue

            txs.append(RealStateCFTx(
                id=uuid4(),
                ref=ref,
                name=name,
                amount=amount,
                currency="EUR",
                type=tx_type,
                date=tx_date,
                entity=WECITY,
                product_type=ProductType.REAL_STATE_CF,
                fees=Dezimal(0),
                retentions=Dezimal(0),
                interests=Dezimal(0),
                net_amount=amount,
                is_real=True
            ))

        return Transactions(investment=txs)

    def scrape_transactions(self):
        raw_txs = self._client.get_transactions()

        txs = []
        for tx in raw_txs:
            txs.append(
                {
                    "date": datetime.fromtimestamp(tx["date"]),
                    "category": tx["type"],
                    "name": tx["title"].strip(),
                    "amount": round(Dezimal(tx["amount"]), 2)
                }
            )

        return sorted(txs, key=lambda txx: (txx["date"], txx["amount"]))

    @staticmethod
    def _calc_tx_id(inv_name: str,
                    tx_date: date,
                    amount: Dezimal,
                    tx_type: TxType) -> str:
        return sha1(
            f"W_{inv_name}_{tx_date.isoformat()}_{amount}_{tx_type}".encode("UTF-8")).hexdigest()

    async def historical_position(self) -> HistoricalPosition:
        txs = self.scrape_transactions()
        investments = self._client.get_investments()

        investment_details = []
        for inv_id, inv in investments.items():
            investment_details.append(self._map_investment(txs, inv_id, inv))

        return HistoricalPosition(
            investments=Investments(
                real_state_cf=RealStateCFInvestments(
                    total=None,
                    weighted_interest_rate=None,
                    details=investment_details
                )
            )
        )
