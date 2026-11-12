from datetime import datetime
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.importing import (
    ImportErrorType,
    ImportRowOrigin,
    TransactionsImportResult,
    exclude_duplicated_txs,
    resolve_account_tx_type,
    stored_entity_ids,
    to_unsigned_tx_values,
)
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    FundPortfolioTx,
    Transactions,
    TxType,
    compute_net_amount,
)


def _entity(name="Bank"):
    return Entity(
        id=uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _account_tx(entity, ref, tx_type=TxType.INFLOW, amount="10", fees="0"):
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name="Movement",
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(2025, 1, 1, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(fees),
        retentions=Dezimal(0),
    )


def _crypto_tx(entity, ref, tx_type=TxType.BUY, amount="100", fees="1"):
    return CryptoCurrencyTx(
        id=uuid4(),
        ref=ref,
        name="Bitcoin",
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(2025, 1, 1, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.CRYPTO,
        currency_amount=Dezimal("0.001"),
        symbol="BTC",
        price=Dezimal(100000),
        fees=Dezimal(fees),
    )


def _portfolio_tx(entity, ref):
    return FundPortfolioTx(
        id=uuid4(),
        ref=ref,
        name="Custody fee",
        amount=Dezimal(5),
        currency="EUR",
        type=TxType.FEE,
        date=datetime(2025, 1, 1, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.FUND_PORTFOLIO,
        portfolio_name="Main",
    )


def _result(account=None, investment=None, created=None, origins=None):
    return TransactionsImportResult(
        transactions=Transactions(investment=investment or [], account=account or []),
        created_entities=set(created or []),
        errors=[],
        origins=origins or {},
    )


class TestResolveAccountTxType:
    @pytest.mark.parametrize(
        "tx_type, amount, expected",
        [
            (None, "10", TxType.INFLOW),
            (None, "-10", TxType.OUTFLOW),
            (None, "0", None),
            (TxType.INFLOW, "10", TxType.INFLOW),
            (TxType.INFLOW, "-10", TxType.OUTFLOW),
            (TxType.OUTFLOW, "10", TxType.OUTFLOW),
            (TxType.OUTFLOW, "-10", TxType.OUTFLOW),
            (TxType.OUTFLOW, "0", TxType.OUTFLOW),
            (TxType.FEE, "-3", TxType.FEE),
            (TxType.FEE, "3", TxType.FEE),
            (TxType.INTEREST, "-1", TxType.INTEREST),
            (TxType.INTEREST, "1", TxType.INTEREST),
        ],
    )
    def test_resolves_type_from_sign(self, tx_type, amount, expected):
        assert resolve_account_tx_type(tx_type, Dezimal(amount)) == expected


class TestToUnsignedTxValues:
    def test_applies_abs_to_monetary_fields_only(self):
        values = {
            "amount": Dezimal("-10"),
            "fees": Dezimal("-1"),
            "retentions": Dezimal("-2"),
            "shares": Dezimal("-3"),
            "price": Dezimal("-4"),
            "currency_amount": Dezimal("-5"),
            "net_amount": Dezimal("-6"),
            "interest_rate": Dezimal("-0.01"),
            "avg_balance": Dezimal("-100"),
            "name": "-name",
        }

        to_unsigned_tx_values(values)

        assert values["amount"] == Dezimal(10)
        assert values["fees"] == Dezimal(1)
        assert values["retentions"] == Dezimal(2)
        assert values["shares"] == Dezimal(3)
        assert values["price"] == Dezimal(4)
        assert values["currency_amount"] == Dezimal(5)
        assert values["net_amount"] == Dezimal(6)
        assert values["interest_rate"] == Dezimal("-0.01")
        assert values["avg_balance"] == Dezimal("-100")
        assert values["name"] == "-name"

    def test_keeps_none_and_missing_fields(self):
        values = {"amount": None}

        to_unsigned_tx_values(values)

        assert values == {"amount": None}


class TestComputeNetAmount:
    def test_outgoing_types_add_costs(self):
        entity = _entity()
        tx = _account_tx(entity, "r", TxType.OUTFLOW, amount="100", fees="2")
        tx.retentions = Dezimal(1)

        assert compute_net_amount(tx) == Dezimal(103)

    def test_incoming_types_subtract_costs(self):
        entity = _entity()
        tx = _account_tx(entity, "r", TxType.INFLOW, amount="100", fees="2")
        tx.retentions = Dezimal(1)

        assert compute_net_amount(tx) == Dezimal(97)

    def test_crypto_buy_and_sell(self):
        entity = _entity()

        assert compute_net_amount(_crypto_tx(entity, "a", TxType.BUY)) == Dezimal(101)
        assert compute_net_amount(_crypto_tx(entity, "b", TxType.SELL)) == Dezimal(99)

    def test_missing_retentions_count_as_zero(self):
        entity = _entity()
        tx = _crypto_tx(entity, "a", TxType.DIVIDEND, amount="10", fees="1")

        assert tx.retentions is None
        assert compute_net_amount(tx) == Dezimal(9)


class TestStoredEntityIds:
    def test_excludes_created_entities(self):
        stored = _entity("Stored")
        created = _entity("Created")
        result = _result(
            account=[_account_tx(stored, "a"), _account_tx(created, "b")],
            investment=[_crypto_tx(stored, "c")],
            created=[created],
        )

        assert stored_entity_ids(result) == [stored.id]

    def test_empty_result(self):
        result = TransactionsImportResult(
            transactions=None, created_entities=set(), errors=[]
        )

        assert stored_entity_ids(result) == []


class TestExcludeDuplicatedTxs:
    def test_skips_existing_refs_and_reports_origin(self):
        entity = _entity()
        kept = _account_tx(entity, "new")
        duplicated = _account_tx(entity, "old")
        row = ["old", "Movement", "10", "EUR"]
        result = _result(
            account=[kept, duplicated],
            origins={
                kept.id: ImportRowOrigin(entry="file.csv", row=["new"]),
                duplicated.id: ImportRowOrigin(entry="file.csv", row=row),
            },
        )

        transactions, errors = exclude_duplicated_txs(
            result, {(entity.id, ProductType.ACCOUNT, "old")}
        )

        assert transactions.account == [kept]
        assert transactions.investment == []
        assert len(errors) == 1
        assert errors[0].type == ImportErrorType.DUPLICATED
        assert errors[0].entry == "file.csv"
        assert errors[0].detail == [{"field": "ref", "value": "old"}]
        assert errors[0].row == row

    def test_skips_repeated_refs_within_batch_keeping_first(self):
        entity = _entity()
        first = _crypto_tx(entity, "dup")
        second = _crypto_tx(entity, "dup")
        result = _result(investment=[first, second])

        transactions, errors = exclude_duplicated_txs(result, set())

        assert transactions.investment == [first]
        assert [error.type for error in errors] == [ImportErrorType.DUPLICATED]
        assert errors[0].entry == ""
        assert errors[0].row is None

    def test_same_ref_in_other_product_or_entity_is_kept(self):
        entity = _entity("A")
        other_entity = _entity("B")
        account = _account_tx(entity, "shared")
        crypto = _crypto_tx(entity, "shared")
        portfolio = _portfolio_tx(entity, "shared")
        other = _account_tx(other_entity, "shared")
        result = _result(account=[account, other], investment=[crypto, portfolio])

        transactions, errors = exclude_duplicated_txs(
            result, {(entity.id, ProductType.STOCK_ETF, "shared")}
        )

        assert transactions.account == [account, other]
        assert transactions.investment == [crypto, portfolio]
        assert errors == []

    def test_handles_empty_transactions(self):
        result = TransactionsImportResult(
            transactions=None, created_entities=set(), errors=[]
        )

        transactions, errors = exclude_duplicated_txs(result, set())

        assert transactions.account == []
        assert transactions.investment == []
        assert errors == []

    def test_does_not_mutate_existing_keys(self):
        entity = _entity()
        existing = {(entity.id, ProductType.ACCOUNT, "old")}
        result = _result(account=[_account_tx(entity, "new")])

        exclude_duplicated_txs(result, existing)

        assert existing == {(entity.id, ProductType.ACCOUNT, "old")}
