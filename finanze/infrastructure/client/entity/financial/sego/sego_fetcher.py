import copy
import logging
from datetime import date, datetime
from hashlib import sha1
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.currency_symbols import SYMBOL_CURRENCY_MAP
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
from pytz import utc

DATETIME_FORMAT = "%d/%m/%Y %H:%M"
TAG_TIME_FORMAT = "%H:%M:%S"

ACTIVE_SEGO_STATES = ["disputa", "gestionando-cobro", "no-llego-fecha-cobro"]
FINISHED_SEGO_STATES = frozenset({"cobrado", "fallido"})


def parse_tag(tag: str) -> dict:
    tag_props = {}
    for e in tag.split(";"):
        k, v = e.split(":", 1)
        tag_props[k] = v

    return tag_props


def map_txs(
    ref: str,
    tx: dict,
    name: str,
    tx_type: TxType,
    amount: Dezimal,
    net_amount: Dezimal,
    fee: Dezimal,
    tax: Dezimal,
) -> Optional[FactoringTx]:
    tx_date = tx["date"]
    currency = tx["currency"]

    return FactoringTx(
        id=uuid4(),
        ref=ref,
        name=name,
        amount=round(amount, 2),
        currency=currency,
        type=tx_type,
        date=tx_date,
        entity=SEGO,
        product_type=ProductType.FACTORING,
        fees=fee,
        retentions=tax,
        net_amount=round(net_amount, 2),
        source=DataSource.REAL,
    )


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

        return self._client.login(
            username, password, login_params.options, code, login_params.session
        )

    async def global_position(self) -> GlobalPosition:
        raw_wallet = self._client.get_wallet()
        wallet_amount = raw_wallet["importe"]
        account = Account(
            id=uuid4(),
            currency="EUR",
            total=round(Dezimal(wallet_amount), 2),
            type=AccountType.VIRTUAL_WALLET,
        )

        investment_movements = self._get_normalized_movements(
            ["TRANSFER"], ["Inversión Factoring"]
        )

        raw_sego_investments = (
            self._client.get_investments() + self._client.get_pending_investments()
        )
        active_sego_investments = [
            investment
            for investment in raw_sego_investments
            if investment["tipoEstadoOperacionCodigo"] in ACTIVE_SEGO_STATES
        ]

        factoring_investments = []
        for investment in active_sego_investments:
            factoring_investments.append(
                self._map_investment(investment_movements, investment)
            )

        products = {
            ProductType.ACCOUNT: Accounts([account]),
            ProductType.FACTORING: FactoringInvestments(
                factoring_investments,
            ),
        }

        return GlobalPosition(id=uuid4(), entity=SEGO, products=products)

    def _map_investment(self, investment_movements, investment) -> FactoringDetail:
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

        last_invest_date = next(
            (
                movement["date"]
                for movement in investment_movements
                if name in movement["mensajeCompleto"]
            ),
            None,
        )

        interest_rate = round(gross_interest_rate * (1 - self.SEGO_FEE) / 100, 4)
        expected_maturity = (
            date.fromisoformat(investment["fechaDevolucion"][:10])
            if investment["fechaDevolucion"]
            else None
        )

        profitability = Dezimal(0)
        if last_invest_date and expected_maturity:
            days = (expected_maturity - last_invest_date.date()).days
            if days > 0:
                profitability = Dezimal(
                    round(interest_rate * Dezimal(days) / Dezimal(365), 4)
                )

        return FactoringDetail(
            id=uuid4(),
            name=name,
            amount=round(Dezimal(investment["importe"]), 2),
            currency="EUR",
            interest_rate=interest_rate,
            profitability=profitability,
            gross_interest_rate=round(gross_interest_rate / 100, 4),
            last_invest_date=last_invest_date,
            maturity=expected_maturity,
            type=proj_type,
            state=state,
        )

    def _get_normalized_movements(self, types=None, subtypes=None) -> list[dict]:
        if subtypes is None:
            subtypes = []
        if types is None:
            types = []

        raw_movements = []
        page = 1
        while True:
            fetched_movs = copy.deepcopy(
                self._client.get_movements(page=page, limit=100)
            )
            raw_movements += fetched_movs

            if len(fetched_movs) < 100:
                break
            page += 1

        normalized_movs = []
        for movement in raw_movements:
            if "Factoring" not in (movement.get("plataforma") or ""):
                continue

            if (not types or movement["type"] in types) and (
                not subtypes or movement["tipo"] in subtypes
            ):
                tag = movement.get("tag", None)
                parsed_tag_time = None
                if tag:
                    tag_props = parse_tag(tag)
                    if raw_tag_time := tag_props.get("date", None):
                        parsed_tag_time = datetime.strptime(
                            raw_tag_time.split(" ")[-1], TAG_TIME_FORMAT
                        )

                mov_datetime = datetime.strptime(
                    movement["creationDate"], DATETIME_FORMAT
                )
                if parsed_tag_time:
                    mov_datetime = mov_datetime.replace(second=parsed_tag_time.second)

                movement["date"] = mov_datetime.replace(tzinfo=utc)

                currency_symbol = movement["amount"][-1]
                currency = SYMBOL_CURRENCY_MAP.get(currency_symbol, "EUR")
                raw_formated_amount = movement["amount"]
                movement["amount"] = Dezimal(
                    raw_formated_amount[2:-1].replace(".", "").replace(",", ".")
                )
                movement["currency"] = currency
                movement["currencySymbol"] = currency_symbol

                normalized_movs.append(movement)

        return sorted(normalized_movs, key=lambda m: m["date"])

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        factoring_txs = self.fetch_factoring_txs(registered_txs)

        return Transactions(investment=factoring_txs)

    def fetch_factoring_txs(self, registered_txs: set[str]) -> list[FactoringTx]:
        completed_investments = self._client.get_investments(FINISHED_SEGO_STATES)

        txs = self._get_normalized_movements(
            ["TRANSFER"],
            [
                "Inversión Factoring",
                "Devolución Capital",
                "Ganancias",
                "Ganancias extraordinarias",
            ],
        )

        investment_txs = []

        for tx in txs:
            tag_props = parse_tag(tx["tag"]) if tx.get("tag", None) else None
            if not tag_props:
                self._log.warning(f"No tag in SEGO transaction: {tx}")
                continue

            investment_name = tag_props["operacion"].strip()
            tx_date = tx["date"]
            raw_tx_type = tx["tipo"]
            if raw_tx_type == "Inversión Factoring":
                tx_type = TxType.INVESTMENT
            elif raw_tx_type == "Devolución Capital":
                tx_type = TxType.REPAYMENT
            elif (
                raw_tx_type == "Ganancias" or raw_tx_type == "Ganancias extraordinarias"
            ):
                tx_type = TxType.INTEREST
            else:
                self._log.warning(f"Unknown transaction type: {raw_tx_type}")
                continue

            amount: Dezimal = tx["amount"]
            ref = self._calc_sego_tx_id(investment_name, tx_date, amount, tx_type)
            if ref in registered_txs:
                continue

            fee, tax = Dezimal(0), Dezimal(0)
            net_amount = amount
            if tx_type == TxType.INTEREST:
                matching_investment = next(
                    (
                        investment
                        for investment in completed_investments
                        if investment["nombreOperacion"].strip() == investment_name
                    ),
                    None,
                )

                ordinary_interests = Dezimal(matching_investment["gananciasOrdinarias"])
                extraordinary_interests = Dezimal(
                    matching_investment["gananciasExtraOrdinarias"]
                )
                total_interests = ordinary_interests + extraordinary_interests
                percentage = amount / total_interests

                fee = round(percentage * Dezimal(matching_investment["comision"]), 2)
                tax = round(percentage * Dezimal(matching_investment["retencion"]), 2)

                net_amount = amount - fee - tax

            stored_tx = map_txs(
                ref, tx, investment_name, tx_type, amount, net_amount, fee, tax
            )
            investment_txs.append(stored_tx)

        return investment_txs

    @staticmethod
    def _calc_sego_tx_id(
        inv_name: str, tx_date: datetime, amount: Dezimal, tx_type: TxType
    ) -> str:
        return sha1(
            f"S_{inv_name}_{tx_date.isoformat()}_{amount}_{tx_type}".encode("UTF-8")
        ).hexdigest()

    async def historical_position(self) -> HistoricalPosition:
        investment_movements = self._get_normalized_movements(
            ["TRANSFER"], ["Inversión Factoring"]
        )

        raw_sego_investments = (
            self._client.get_investments() + self._client.get_pending_investments()
        )
        active_sego_investments = [investment for investment in raw_sego_investments]

        factoring_investments = []
        for investment in active_sego_investments:
            factoring_investments.append(
                self._map_investment(investment_movements, investment)
            )

        return HistoricalPosition(
            {ProductType.FACTORING: FactoringInvestments(factoring_investments)}
        )
