from datetime import datetime, date
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from application.ports.entity_scraper import EntityScraper
from domain.dezimal import Dezimal
from domain.financial_entity import UNICAJA
from domain.global_position import Account, Card, Mortgage, GlobalPosition, CardType, AccountType
from infrastructure.scrapers.unicaja.unicaja_client import UnicajaClient


class UnicajaScraper(EntityScraper):

    def __init__(self):
        self._client = UnicajaClient()

    async def login(self, credentials: tuple, **kwargs) -> dict:
        username, password = credentials
        return self._client.login(username, password)

    async def global_position(self) -> GlobalPosition:
        accounts_response = self._client.list_accounts()

        accounts = [self._map_account(account_data_raw) for account_data_raw in accounts_response["cuentas"]]

        card_list = self._client.get_cards()["tarjetas"]

        cards = [self._map_base_card(card_data_raw, accounts) for card_data_raw in card_list]

        # debit_card_raw = next((card for card in card_list if card["codtipotarjeta"] == "1"), None)
        # if debit_card_raw:
        #     related_account = next((account for account in accounts if account.iban == debit_card_raw["ibancuenta"]),
        #                            None)
        #     related_account = None if not related_account else related_account.id
        #
        #     description = debit_card_raw["tipotarjeta"]
        #     alias = debit_card_raw["alias"]
        #     name = alias if alias else description
        #
        #     debit_card_ending = debit_card_raw["numtarjeta"].split(" ")[-1]
        #
        #     debit_card_details_raw = self._client.get_card(debit_card_raw["ppp"], debit_card_raw["codtipotarjeta"])
        #     deferred_debit_amount = Dezimal(debit_card_details_raw["datosCredito"]["importeDispuesto"]["cantidad"])
        #
        #     cards += Card(
        #         id=uuid4(),
        #         name=name,
        #         ending=debit_card_ending,
        #         type=CardType.DEBIT,
        #         limit=Dezimal(debit_card_raw["limite"]["cantidad"]),  # ??
        #         used=Dezimal(debit_card_raw["pagadoMesActual"]["cantidad"]) + deferred_debit_amount,
        #         related_account=related_account
        #     )
        #
        # credit_card_raw = next((card for card in card_list if card["codtipotarjeta"] == "2"), None)
        # if credit_card_raw:
        #     related_account = next((account for account in accounts if account.iban == debit_card_raw["ibancuenta"]),
        #                            None)
        #     related_account = None if not related_account else related_account.id
        #
        #     description = debit_card_raw["tipotarjeta"]
        #     alias = debit_card_raw["alias"]
        #     name = alias if alias else description
        #
        #     credit_card_ending = debit_card_raw["numtarjeta"].split(" ")[-1]
        #
        #     cards += Card(
        #         id=uuid4(),
        #         name=name,
        #         ending=credit_card_ending,
        #         type=CardType.CREDIT,
        #         limit=Dezimal(credit_card_raw["limite"]["cantidad"]),
        #         used=Dezimal(credit_card_raw["limite"]["cantidad"]) - Dezimal(
        #             credit_card_raw["disponible"]["cantidad"]),
        #         related_account=related_account
        #     )

        self._client.get_loans()
        mortgage_response = self._client.get_loan(p="2", ppp="001")
        mortgage_data = None
        # When its near invoicing period, the mortgage is not returned
        if mortgage_response:
            mortgage_data = Mortgage(
                id=uuid4(),
                name="",
                currency='EUR',
                current_installment=Dezimal(mortgage_response["currentInstallment"]),
                loan_amount=Dezimal(mortgage_response["loanAmount"]),
                principal_paid=Dezimal(mortgage_response["principalPaid"]),
                principal_outstanding=Dezimal(mortgage_response["principalOutstanding"]),
                interest_rate=Dezimal(mortgage_response["interestRate"]),
                next_payment_date=datetime.strptime(mortgage_response["nextPaymentDate"], "%Y-%m-%d").date(),
            )

        return GlobalPosition(
            id=uuid4(),
            entity=UNICAJA,
            account=accounts,
            cards=cards,
            mortgage=[mortgage_data],
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
        currency = card_data_raw["divisa"]

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
