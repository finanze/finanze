import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
    ContributionTargetSubtype,
)
from domain.dezimal import Dezimal
from domain.native_entity import EntitySetupLoginType
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_pointer import FetchPointer
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    GlobalPosition,
    Loan,
    Loans,
    LoanType,
    ProductType,
)
from domain.native_entities import UNICAJA
from domain.transactions import (
    ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS,
    AccountTx,
    Transactions,
    TxType,
    normalize_iban,
)
from infrastructure.client.entity.financial.unicaja.unicaja_client import UnicajaClient

CONTRIBUTION_FREQUENCY = {
    "M": ContributionFrequency.MONTHLY,
    "T": ContributionFrequency.QUARTERLY,
    "S": ContributionFrequency.SEMIANNUAL,
    "A": ContributionFrequency.YEARLY,
}

ACCOUNT_TXS_POINTER = "account_txs"
MAX_MOVEMENT_PAGES = 50
MOVEMENT_DATE_FORMAT = "%Y-%m-%d"


class UnicajaFetcher(FinancialEntityFetcher):
    def __init__(self, use_mobile_client: bool = False):
        self._client = UnicajaClient(use_mobile_client=use_mobile_client)

        self._log = logging.getLogger(__name__)

        self._abck = os.getenv("UNICAJA_ABCK")
        if self._abck:
            UNICAJA.setup_login_type = EntitySetupLoginType.AUTOMATED

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        abck = self._abck or credentials.get("abck")
        return await self._client.login(username, password, abck)

    async def global_position(self) -> GlobalPosition:
        accounts_response = await self._client.list_accounts()

        accounts = [
            await self._map_account(account_data_raw)
            for account_data_raw in accounts_response["cuentas"]
        ]

        card_list = (await self._client.get_cards())["tarjetas"]

        cards = []
        for card_data_raw in card_list:
            try:
                cards.append(await self._map_base_card(card_data_raw, accounts))
            except (KeyError, TypeError, ValueError, ArithmeticError) as e:
                self._log.warning(
                    f"Skipping Unicaja card ending {(card_data_raw.get('numtarjeta') or '')[-4:]} "
                    f"due to missing or invalid data: {e!r}"
                )

        raw_loans = (await self._client.get_loans())["prestamos"]
        loans = [await self._get_loan(loan_data_raw) for loan_data_raw in raw_loans]
        loans = [loan for loan in loans if loan is not None]

        products = {
            ProductType.ACCOUNT: Accounts(accounts),
            ProductType.CARD: Cards(cards),
            ProductType.LOAN: Loans(loans),
        }

        return GlobalPosition(
            id=uuid4(),
            entity=UNICAJA,
            products=products,
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        accounts_response = await self._client.list_accounts()
        account_txs = []
        for account in accounts_response.get("cuentas") or []:
            account_txs += await self._fetch_account_movements(
                account, registered_txs, options
            )
        return Transactions(investment=[], account=account_txs)

    async def _fetch_account_movements(
        self, account: dict, registered_txs: set[str], options: FetchOptions
    ) -> list[AccountTx]:
        ppp = account["ppp"]
        iban = account["iban"]
        today = date.today()
        pointer_key = f"{ACCOUNT_TXS_POINTER}:{iban}"
        min_date = today - timedelta(days=ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS)
        pointer = self._get_pointer(options, pointer_key)
        if pointer:
            min_date = min(pointer.threshold, today)

        txs = []
        latest_date: Optional[date] = None
        last_balance = last_movement = None
        for _ in range(MAX_MOVEMENT_PAGES):
            page = await self._client.get_account_movements(
                ppp, last_balance, last_movement
            )
            reached_end = False
            for movement in page.get("movimientos") or []:
                tx_date = datetime.strptime(
                    movement["fechaOperacion"], MOVEMENT_DATE_FORMAT
                ).date()
                if latest_date is None or tx_date > latest_date:
                    latest_date = tx_date
                if tx_date < min_date:
                    reached_end = True
                    continue

                ref = f"{iban}:{movement['numMovimiento']}"
                if ref in registered_txs:
                    reached_end = True
                    continue

                tx = self._map_account_movement(movement, ref, tx_date, iban)
                if tx:
                    txs.append(tx)

            more = page.get("masMovimientos") or {}
            if reached_end or more.get("indMasMovimientos") != "S":
                break
            if more.get("indOTP") == "S":
                self._log.info("Older Unicaja movements require OTP, stopping")
                break
            last_balance = str((more.get("ultimoSaldo") or {}).get("cantidad"))
            last_movement = str(more.get("numUltimoMovimiento"))

        self._update_pointer(options, pointer_key, latest_date or today)
        return txs

    @staticmethod
    def _map_account_movement(
        movement: dict, ref: str, tx_date: date, iban: Optional[str] = None
    ) -> Optional[AccountTx]:
        raw_amount = Dezimal(str(movement["importeMovimiento"]["cantidad"]))
        if raw_amount == 0:
            return None
        amount = abs(raw_amount)
        return AccountTx(
            id=uuid4(),
            ref=ref,
            name=(movement.get("concepto") or "").strip(),
            amount=amount,
            currency=movement["importeMovimiento"].get("moneda") or "EUR",
            type=TxType.INFLOW if raw_amount > 0 else TxType.OUTFLOW,
            date=datetime.combine(tx_date, datetime.min.time(), tzinfo=tzlocal()),
            entity=UNICAJA,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal(0),
            retentions=Dezimal(0),
            net_amount=amount,
            iban=normalize_iban(iban),
        )

    @staticmethod
    def _get_pointer(
        options: Optional[FetchOptions], key: str
    ) -> Optional[FetchPointer]:
        if not options or not options.pointer_context:
            return None
        return options.pointer_context.pointers.get(key)

    @staticmethod
    def _update_pointer(options: Optional[FetchOptions], key: str, threshold: date):
        if not options or not options.pointer_context:
            return
        options.pointer_context.pointers[key] = FetchPointer(
            entity_id=options.pointer_context.entity_id,
            entity_account_id=options.pointer_context.entity_account_id,
            key=key,
            threshold=threshold,
        )

    async def _map_account(self, account_data_raw):
        account_alias = account_data_raw["alias"]
        account_desc = account_data_raw["descripcion"]
        name = account_alias if account_alias else account_desc
        iban = account_data_raw["iban"]
        account_balance = Dezimal(account_data_raw["saldo"]["cantidad"])
        account_currency = account_data_raw["saldo"]["moneda"]
        account_available = Dezimal(account_data_raw["disponible"]["cantidad"])
        account_allowed_overdraft = Dezimal(
            account_data_raw["importeExcedido"]["cantidad"]
        )
        account_pending_payments = round(
            account_balance + account_allowed_overdraft - account_available, 2
        )
        last_week_date = date.today() - relativedelta(weeks=1)
        account_pending_transfers_raw = await self._client.get_transfers_historic(
            from_date=last_week_date
        )
        account_pending_transfer_amount = Dezimal(0)
        if "noDatos" not in account_pending_transfers_raw:
            account_pending_transfer_amount = sum(
                Dezimal(transfer["importe"]["cantidad"])
                for transfer in account_pending_transfers_raw["transferencias"]
                if transfer["estadoTransferencia"] == "P"
            )
        account_data = Account(
            id=uuid4(),
            total=account_balance,
            currency=account_currency,
            iban=iban,
            name=name,
            type=AccountType.CHECKING,
            retained=account_pending_payments,
            interest=Dezimal(0),  # :(
            pending_transfers=account_pending_transfer_amount,
        )
        return account_data

    async def _map_base_card(self, card_data_raw, accounts: list[Account]):
        related_account = next(
            (
                account
                for account in accounts
                if account.iban == card_data_raw["ibancuenta"]
            ),
            None,
        )
        related_account = None if not related_account else related_account.id

        description = card_data_raw["tipotarjeta"]
        alias = card_data_raw["alias"]
        name = alias if alias else description

        card_ending = card_data_raw["numtarjeta"].split(" ")[-1]

        active = card_data_raw["estado"] == "E"

        card_type = CardType.DEBIT
        if card_data_raw["codtipotarjeta"] == "2":
            card_type = CardType.CREDIT

        limit = Dezimal(card_data_raw["limite"]["cantidad"])
        used = Dezimal(0)
        currency = card_data_raw["limite"]["moneda"]

        if card_type == CardType.DEBIT:
            debit_card_details_raw = await self._client.get_card(
                card_data_raw["ppp"], card_data_raw["codtipotarjeta"]
            )
            deferred_debit_amount = Dezimal(
                debit_card_details_raw["datosCredito"]["importeDispuesto"]["cantidad"]
            )

            used = (
                Dezimal(card_data_raw["pagadoMesActual"]["cantidad"])
                + deferred_debit_amount
            )

        elif card_type == CardType.CREDIT:
            used = Dezimal(card_data_raw["limite"]["cantidad"]) - Dezimal(
                card_data_raw["disponible"]["cantidad"]
            )

        return Card(
            id=uuid4(),
            name=name,
            ending=card_ending,
            currency=currency,
            type=card_type,
            limit=limit,
            used=used,
            active=active,
            related_account=related_account,
        )

    async def _get_loan(self, loan_entry):
        active = loan_entry["estado"] == "ACTIVO"
        if not active:
            return None

        ppp = loan_entry["ppp"]
        is_mortgage = loan_entry["indPrestamoHipotecario"] == "S"
        outstanding_amount = Dezimal(loan_entry["saldo"]["cantidad"])
        currency = loan_entry["saldo"]["moneda"]
        alias = loan_entry["alias"]

        loan_type = LoanType.MORTGAGE if is_mortgage else LoanType.STANDARD

        loan_response = await self._client.get_loan(ppp=ppp)
        if loan_response:
            loan_response = loan_response["detallePrestamo"]

        if loan_response:
            name = alias if alias else loan_response["tipoPrestamo"]
            return Loan(
                id=uuid4(),
                type=loan_type,
                name=name,
                currency=currency,
                current_installment=Dezimal(loan_response["cuotaActual"]["cantidad"]),
                loan_amount=Dezimal(loan_response["importePrestamo"]["cantidad"]),
                principal_outstanding=outstanding_amount,
                interest_rate=Dezimal(loan_response["interes"]) / 100,
                next_payment_date=datetime.strptime(
                    loan_response["fechaProxRecibo"], "%Y-%m-%d"
                ).date(),
                creation=datetime.strptime(
                    loan_response["fechaApertura"], "%Y-%m-%d"
                ).date(),
                maturity=datetime.strptime(
                    loan_response["fechaVencimiento"], "%Y-%m-%d"
                ).date(),
                unpaid=Dezimal(loan_response["recibosImpagados"]["cantidad"]),
            )

        return None

    async def auto_contributions(self) -> AutoContributions:
        try:
            fund_accounts = await self._client.list_fund_accounts()
            first_account = (
                fund_accounts["cuentasFondos"][0]
                if "cuentasFondos" in fund_accounts and fund_accounts["cuentasFondos"]
                else None
            )
            if not first_account:
                self._log.info("No fund accounts found for contributions.")
                return AutoContributions(periodic=[])

            account_code = first_account["cuenta"]

            periodic_subs = await self._client.get_periodic_subscriptions(account_code)
        except Exception as e:
            self._log.error(
                f"Error fetching periodic subscriptions, maybe there aren't: {e}"
            )
            return AutoContributions(periodic=[])

        if "misSuscripciones" not in periodic_subs:
            return AutoContributions(periodic=[])

        periodic = []
        for sub in periodic_subs["misSuscripciones"]:
            raw_frequency = sub["periodicidad"]
            frequency = CONTRIBUTION_FREQUENCY.get(raw_frequency)
            if not frequency:
                self._log.warning(f"Unknown contribution frequency: {raw_frequency}")
                continue

            active = sub.get("estado", "DESACTIVADA") == "ACTIVA"
            isin = sub["isin"]
            name = sub.get("nombreFondo", isin)
            amount = Dezimal(sub["impOperPeriodica"]["cantidad"])
            currency = sub["impOperPeriodica"]["moneda"]

            periodic.append(
                PeriodicContribution(
                    id=uuid4(),
                    alias=name,
                    target=isin,
                    target_name=name,
                    target_type=ContributionTargetType.FUND,
                    target_subtype=ContributionTargetSubtype.MUTUAL_FUND,
                    amount=amount,
                    currency=currency,
                    since=datetime.strptime(sub["fechaAlta"], "%Y-%m-%d").date(),
                    until=(
                        datetime.strptime(sub["fechaLimite"], "%Y-%m-%d").date()
                        if sub.get("fechaLimite")
                        else None
                    ),
                    frequency=frequency,
                    active=active,
                    source=DataSource.REAL,
                )
            )

        return AutoContributions(periodic)
