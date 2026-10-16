from uuid import uuid4

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.transactions import TxType
from infrastructure.client.entity.financial.psd2.psd2_transactions import (
    map_enablebanking_transaction,
    map_gocardless_transaction,
)

ENTITY = Entity(
    id=uuid4(),
    name="Bank",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.EXTERNALLY_PROVIDED,
    icon_url=None,
)


def _eb_tx(**overrides):
    tx = {
        "entry_reference": "E1",
        "transaction_amount": {"currency": "EUR", "amount": "45.20"},
        "creditor": {"name": "Mercadona SA"},
        "debtor": {"name": "Me"},
        "credit_debit_indicator": "DBIT",
        "status": "BOOK",
        "booking_date": "2026-09-10",
        "remittance_information": ["COMPRA", "  MERCADONA   VALENCIA "],
    }
    tx.update(overrides)
    return tx


class TestEnableBankingMapping:
    def test_debit_maps_to_outflow_with_creditor_counterparty(self):
        tx = map_enablebanking_transaction(_eb_tx(), "ES00", ENTITY, "es00 1234")

        assert tx.type == TxType.OUTFLOW
        assert tx.amount == Dezimal("45.20")
        assert tx.counterparty == "Mercadona SA"
        assert tx.name == "COMPRA MERCADONA VALENCIA"
        assert tx.ref == "ES00:E1"
        assert tx.iban == "ES001234"
        assert tx.date.date().isoformat() == "2026-09-10"

    def test_credit_maps_to_inflow_with_debtor_counterparty(self):
        tx = map_enablebanking_transaction(
            _eb_tx(credit_debit_indicator="CRDT", debtor={"name": "Employer"}),
            "ES00",
            ENTITY,
        )

        assert tx.type == TxType.INFLOW
        assert tx.counterparty == "Employer"

    def test_pending_transactions_are_skipped(self):
        assert (
            map_enablebanking_transaction(_eb_tx(status="PDNG"), "ES00", ENTITY) is None
        )

    def test_missing_entry_reference_uses_stable_hash(self):
        first = map_enablebanking_transaction(
            _eb_tx(entry_reference=None), "ES00", ENTITY
        )
        second = map_enablebanking_transaction(
            _eb_tx(entry_reference=None), "ES00", ENTITY
        )

        assert first.ref == second.ref
        assert first.ref.startswith("ES00:h")

    def test_name_falls_back_to_bank_transaction_code(self):
        tx = map_enablebanking_transaction(
            _eb_tx(
                remittance_information=None,
                bank_transaction_code={"description": "Card payment"},
            ),
            "ES00",
            ENTITY,
        )

        assert tx.name == "Card payment"


class TestGoCardlessMapping:
    def test_sign_decides_direction(self):
        outflow = map_gocardless_transaction(
            {
                "transactionId": "T1",
                "bookingDate": "2026-09-01",
                "transactionAmount": {"amount": "-12.99", "currency": "EUR"},
                "creditorName": "Netflix",
                "remittanceInformationUnstructured": "NETFLIX.COM",
            },
            "ES11",
            ENTITY,
        )
        inflow = map_gocardless_transaction(
            {
                "internalTransactionId": "I2",
                "bookingDate": "2026-09-02",
                "transactionAmount": {"amount": "1500.00", "currency": "EUR"},
                "debtorName": "ACME",
                "remittanceInformationUnstructuredArray": ["NOMINA", "SEPT"],
            },
            "ES11",
            ENTITY,
        )

        assert outflow.type == TxType.OUTFLOW
        assert outflow.amount == Dezimal("12.99")
        assert outflow.counterparty == "Netflix"
        assert outflow.ref == "ES11:T1"
        assert outflow.iban is None
        assert inflow.type == TxType.INFLOW
        assert inflow.name == "NOMINA SEPT"
        assert inflow.counterparty == "ACME"
        assert inflow.ref == "ES11:I2"

    def test_zero_amount_is_skipped(self):
        assert (
            map_gocardless_transaction(
                {
                    "transactionId": "T0",
                    "bookingDate": "2026-09-01",
                    "transactionAmount": {"amount": "0", "currency": "EUR"},
                },
                "ES11",
                ENTITY,
            )
            is None
        )
