import logging
import os
from datetime import date, datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.relativedelta import relativedelta
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
from domain.fetch_record import DataSource
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
from infrastructure.client.entity.financial.unicaja.unicaja_client import UnicajaClient

CONTRIBUTION_FREQUENCY = {
    "M": ContributionFrequency.MONTHLY,
    "T": ContributionFrequency.QUARTERLY,
    "S": ContributionFrequency.SEMIANNUAL,
    "A": ContributionFrequency.YEARLY,
}


class UnicajaFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = UnicajaClient()

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

        cards = [
            await self._map_base_card(card_data_raw, accounts)
            for card_data_raw in card_list
        ]

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
                principal_paid=Dezimal(loan_response["capitalPagado"]["cantidad"]),
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
                    until=datetime.strptime(sub["fechaLimite"], "%Y-%m-%d").date()
                    if sub.get("fechaLimite")
                    else None,
                    frequency=frequency,
                    active=active,
                    source=DataSource.REAL,
                )
            )

        return AutoContributions(periodic)
