from datetime import datetime, date
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from application.ports.entity_scraper import EntityScraper
from domain.dezimal import Dezimal
from domain.global_position import Account, Card, Loan, GlobalPosition, CardType, AccountType, LoanType
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.native_entities import UNICAJA
from infrastructure.scrapers.unicaja.unicaja_client import UnicajaClient


class UnicajaScraper(EntityScraper):

    def __init__(self):
        self._client = UnicajaClient()

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        return self._client.login(username, password)

    async def global_position(self) -> GlobalPosition:
        accounts_response = self._client.list_accounts()

        accounts = [self._map_account(account_data_raw) for account_data_raw in accounts_response["cuentas"]]

        card_list = self._client.get_cards()["tarjetas"]

        cards = [self._map_base_card(card_data_raw, accounts) for card_data_raw in card_list]

        raw_loans = self._client.get_loans()["prestamos"]
        loans = [self._get_loan(loan_data_raw) for loan_data_raw in raw_loans]
        loans = [loan for loan in loans if loan is not None]

        return GlobalPosition(
            id=uuid4(),
            entity=UNICAJA,
            accounts=accounts,
            cards=cards,
            loans=loans,
        )

    def _map_account(self, account_data_raw):
        account_alias = account_data_raw["alias"]
        account_desc = account_data_raw["descripcion"]
        name = account_alias if account_alias else account_desc
        iban = account_data_raw["iban"]
        account_balance = Dezimal(account_data_raw["saldo"]["cantidad"])
        account_currency = account_data_raw["saldo"]["moneda"]
        account_available = Dezimal(account_data_raw["disponible"]["cantidad"])
        account_allowed_overdraft = Dezimal(account_data_raw["importeExcedido"]["cantidad"])
        account_pending_payments = round(
            account_balance + account_allowed_overdraft - account_available, 2
        )
        last_week_date = date.today() - relativedelta(weeks=1)
        account_pending_transfers_raw = self._client.get_transfers_historic(from_date=last_week_date)
        account_pending_transfer_amount = Dezimal(0)
        if "noDatos" not in account_pending_transfers_raw:
            account_pending_transfer_amount = sum(
                Dezimal(transfer["importe"]["cantidad"]) for transfer in account_pending_transfers_raw["transferencias"]
                if
                transfer["estadoTransferencia"] == "P"
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
            pending_transfers=account_pending_transfer_amount
        )
        return account_data

    def _map_base_card(self, card_data_raw, accounts: list[Account]):
        related_account = next((account for account in accounts if account.iban == card_data_raw["ibancuenta"]),
                               None)
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
            debit_card_details_raw = self._client.get_card(card_data_raw["ppp"], card_data_raw["codtipotarjeta"])
            deferred_debit_amount = Dezimal(debit_card_details_raw["datosCredito"]["importeDispuesto"]["cantidad"])

            used = Dezimal(card_data_raw["pagadoMesActual"]["cantidad"]) + deferred_debit_amount

        elif card_type == CardType.CREDIT:
            used = Dezimal(card_data_raw["limite"]["cantidad"]) - Dezimal(card_data_raw["disponible"]["cantidad"])

        return Card(
            id=uuid4(),
            name=name,
            ending=card_ending,
            currency=currency,
            type=card_type,
            limit=limit,
            used=used,
            active=active,
            related_account=related_account
        )

    def _get_loan(self, loan_entry):
        active = loan_entry["estado"] == "ACTIVO"
        if not active:
            return None

        ppp = loan_entry["ppp"]
        is_mortgage = loan_entry["indPrestamoHipotecario"] == "S"
        outstanding_amount = Dezimal(loan_entry["saldo"]["cantidad"])
        currency = loan_entry["saldo"]["moneda"]
        alias = loan_entry["alias"]

        loan_type = LoanType.MORTGAGE if is_mortgage else LoanType.STANDARD

        loan_response = self._client.get_loan(p="2", ppp=ppp)
        # When its near invoicing period, the mortgage is not returned
        if loan_response:
            name = alias if alias else loan_response["loanType"]
            return Loan(
                id=uuid4(),
                type=loan_type,
                name=name,
                currency=currency,
                current_installment=Dezimal(loan_response["currentInstallment"]),
                loan_amount=Dezimal(loan_response["loanAmount"]),
                principal_paid=Dezimal(loan_response["principalPaid"]),
                principal_outstanding=outstanding_amount,
                interest_rate=Dezimal(loan_response["interestRate"]),
                next_payment_date=datetime.strptime(loan_response["nextPaymentDate"], "%Y-%m-%d").date(),
            )

        return None
