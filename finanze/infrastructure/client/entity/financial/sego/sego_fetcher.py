import logging
from datetime import date, datetime
from hashlib import sha1
from typing import Any, Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    FactoringDetail,
    FactoringInvestments,
    GlobalPosition,
    HistoricalPosition,
    ProductType,
)
from domain.native_entities import SEGO
from domain.transactions import FactoringTx, Transactions, TxType
from infrastructure.client.entity.financial.sego.sego_client import SegoAPIClient

ACTIVE_SEGO_STATES = ["disputa", "gestionando-cobro", "no-llego-fecha-cobro"]


class SegoFetcher(FinancialEntityFetcher):
    SEGO_FEE = Dezimal(0.2)

    def __init__(self):
        self._client = SegoAPIClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        two_factor = login_params.two_factor

        username, password = credentials["user"], credentials["password"]
        code = None
        if two_factor:
            code = two_factor.code

        return await self._client.login(
            username, password, login_params.options, code, login_params.session
        )

    async def global_position(self) -> GlobalPosition:
        raw_wallet = await self._client.get_wallet()
        wallet_amount = raw_wallet["importe"]
        account = Account(
            id=uuid4(),
            currency="EUR",
            total=round(Dezimal(wallet_amount), 2),
            type=AccountType.VIRTUAL_WALLET,
        )

        raw_sego_investments = (
            await self._client.get_investments()
            + await self._client.get_pending_investments()
        )
        active_sego_investments = [
            investment
            for investment in raw_sego_investments
            if investment["tipoEstadoOperacionCodigo"] in ACTIVE_SEGO_STATES
        ]

        factoring_investments = []
        for investment in active_sego_investments:
            mapped_inv = self._map_investment(investment)
            if mapped_inv:
                factoring_investments.append(mapped_inv)

        products = {
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.FACTORING: FactoringInvestments(
                factoring_investments,
            ),
        }

        return GlobalPosition(id=uuid4(), entity=SEGO, products=products)

    def _map_investment(self, investment) -> FactoringDetail | None:
        raw_proj_type = investment["tipoOperacionCodigo"]
        proj_type = None
        if raw_proj_type == "admin-publica":
            proj_type = "PUBLIC_ADMIN"
        elif raw_proj_type == "con-seguro":
            proj_type = "INSURED"
        elif raw_proj_type == "sin-seguro":
            proj_type = "NON_INSURED"

        raw_state = investment["tipoEstadoOperacionCodigo"]
        state = "DISPUTE"
        if raw_state == "no-llego-fecha-cobro":
            state = "MATURITY_NOT_REACHED"
        elif raw_state == "gestionando-cobro":
            state = "MANAGING_COLLECTION"
        elif raw_state == "fallido":
            state = "FAILED"
        elif raw_state == "cobrado":
            state = "COLLECTED"

        name = investment["nombreOperacion"].strip()
        gross_interest_rate = Dezimal(investment["tasaInteres"])
        raw_gross_late_interest_rate = investment.get("tasaInteresDemora")
        gross_late_interest_rate = (
            Dezimal(raw_gross_late_interest_rate)
            if raw_gross_late_interest_rate
            else None
        )

        raw_invest_date = investment.get("fechaCreacion")
        if not raw_invest_date:
            self._log.warning(f"No investment date for SEGO investment: {investment}")
            return None
        last_invest_date = datetime.fromisoformat(raw_invest_date)

        interest_rate = round(gross_interest_rate * (1 - self.SEGO_FEE) / 100, 4)
        late_interest_rate = (
            round(gross_late_interest_rate * (1 - self.SEGO_FEE) / 100, 4)
            if gross_late_interest_rate is not None
            else None
        )
        expected_maturity = (
            date.fromisoformat(investment["fechaDevolucion"][:10])
            if investment["fechaDevolucion"]
            else None
        )

        return FactoringDetail(
            id=uuid4(),
            name=name,
            amount=round(Dezimal(investment["importe"]), 2),
            currency="EUR",
            interest_rate=interest_rate,
            late_interest_rate=late_interest_rate,
            last_invest_date=last_invest_date,
            start=last_invest_date,
            maturity=expected_maturity,
            type=proj_type,
            state=state,
            gross_interest_rate=round(gross_interest_rate / 100, 4),
            gross_late_interest_rate=round(gross_late_interest_rate / 100, 4),
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        factoring_txs = await self.fetch_factoring_txs(registered_txs)

        return Transactions(investment=factoring_txs)

    async def fetch_factoring_txs(self, registered_txs: set[str]) -> list[FactoringTx]:
        raw_sego_investments = (
            await self._client.get_investments()
            + await self._client.get_pending_investments()
        )

        investment_txs = []
        for inv in raw_sego_investments:
            name = inv.get("nombreOperacion")
            if not name:
                self._log.warning("SEGO investment without a name")
                continue

            draft_txs = []

            amount = Dezimal(inv["importe"])
            investment_op_id = inv.get("inversionOperacionId")

            investment_tx = self.map_txs(
                name, inv.get("fechaCreacion"), TxType.INVESTMENT, amount, amount
            )
            draft_txs.append(investment_tx)

            raw_repayment_date = inv.get("fechaDePago")
            if raw_repayment_date:
                repayment_tx = self.map_txs(
                    name, raw_repayment_date, TxType.REPAYMENT, amount, amount
                )
                draft_txs.append(repayment_tx)

                ordinary_interests = Dezimal(inv["gananciasOrdinarias"])
                late_interests = Dezimal(inv["gananciasExtraOrdinarias"])
                fees = Dezimal(inv["comision"])
                retention = Dezimal(inv["retencion"])

                if ordinary_interests and ordinary_interests > 0:
                    ordinary_fees = round(
                        (ordinary_interests / (ordinary_interests + late_interests))
                        * fees,
                        2,
                    )
                    ordinary_retention = round(
                        (ordinary_interests / (ordinary_interests + late_interests))
                        * retention,
                        2,
                    )
                    interest_tx = self.map_txs(
                        name,
                        raw_repayment_date,
                        TxType.INTEREST,
                        ordinary_interests,
                        ordinary_interests - ordinary_fees - ordinary_retention,
                        ordinary_fees,
                        ordinary_retention,
                    )
                    draft_txs.append(interest_tx)

                if late_interests and late_interests > 0:
                    late_fees = round(
                        (late_interests / (ordinary_interests + late_interests)) * fees,
                        2,
                    )
                    late_retention = round(
                        (late_interests / (ordinary_interests + late_interests))
                        * retention,
                        2,
                    )
                    late_interest_tx = self.map_txs(
                        name,
                        raw_repayment_date,
                        TxType.INTEREST,
                        late_interests,
                        late_interests - late_fees - late_retention,
                        late_fees,
                        late_retention,
                    )
                    draft_txs.append(late_interest_tx)

            for draft_tx in draft_txs:
                ref = self._calc_sego_tx_id(
                    name, draft_tx.date, amount, draft_tx.type, investment_op_id
                )
                if ref in registered_txs:
                    continue

                draft_tx.ref = ref

                investment_txs.append(draft_tx)

        return investment_txs

    @staticmethod
    def _calc_sego_tx_id(
        inv_name: str,
        tx_date: datetime,
        amount: Dezimal,
        tx_type: TxType,
        investment_op_id: Any,
    ) -> str:
        return sha1(
            f"S_{inv_name}_{investment_op_id}_{tx_date.isoformat()}_{amount}_{tx_type}".encode(
                "UTF-8"
            )
        ).hexdigest()

    @staticmethod
    def map_txs(
        name: str,
        raw_date: str,
        tx_type: TxType,
        amount: Dezimal,
        net_amount: Dezimal,
        fee: Optional[Dezimal] = Dezimal(0),
        tax: Optional[Dezimal] = Dezimal(0),
    ) -> Optional[FactoringTx]:
        tx_date = datetime.fromisoformat(raw_date)

        return FactoringTx(
            id=uuid4(),
            ref="",
            name=name,
            amount=round(Dezimal(amount), 2),
            currency="EUR",
            type=tx_type,
            date=tx_date,
            entity=SEGO,
            product_type=ProductType.FACTORING,
            fees=round(Dezimal(fee), 2),
            retentions=round(Dezimal(tax), 2),
            net_amount=round(Dezimal(net_amount), 2),
            source=DataSource.REAL,
        )

    async def historical_position(self) -> HistoricalPosition:
        raw_sego_investments = (
            await self._client.get_investments()
            + await self._client.get_pending_investments()
        )

        factoring_investments = []
        for investment in raw_sego_investments:
            mapped_inv = self._map_investment(investment)
            if mapped_inv:
                factoring_investments.append(mapped_inv)

        return HistoricalPosition(
            {ProductType.FACTORING: FactoringInvestments(factoring_investments)}
        )
