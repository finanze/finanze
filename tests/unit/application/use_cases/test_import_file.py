from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.entity_port import EntityPort
from application.ports.file_rw_port import TableRWPort
from application.ports.position_port import PositionPort
from application.ports.template_parser_port import TemplateParserPort
from application.ports.template_port import TemplatePort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.import_file import ImportFileImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.export import NumberFormat
from domain.fetch_record import DataSource
from domain.file_upload import FileUpload
from domain.global_position import ProductType
from domain.importing import (
    ImportError,
    ImportErrorType,
    ImportFileRequest,
    ImportResultCode,
    ImportRowOrigin,
    TransactionsImportResult,
)
from domain.settings import TemplateConfig
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    Transactions,
    TxType,
)


def _entity(name):
    return Entity(
        id=uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _account_tx(entity, ref):
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name="Movement",
        amount=Dezimal(10),
        currency="EUR",
        type=TxType.INFLOW,
        date=datetime(2025, 1, 1, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=Dezimal(10),
    )


def _crypto_tx(entity, ref):
    return CryptoCurrencyTx(
        id=uuid4(),
        ref=ref,
        name="Bitcoin",
        amount=Dezimal(100),
        currency="EUR",
        type=TxType.BUY,
        date=datetime(2025, 1, 1, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.MANUAL,
        product_type=ProductType.CRYPTO,
        currency_amount=Dezimal("0.001"),
        symbol="BTC",
        price=Dezimal(100000),
        fees=Dezimal(0),
        net_amount=Dezimal(100),
    )


def _template():
    return Template(
        id=uuid4(),
        name="Import",
        feature=Feature.TRANSACTIONS,
        type=TemplateType.IMPORT,
        fields=[TemplatedField(field="ref", name="ref")],
        products=[ProductType.ACCOUNT],
    )


def _request(preview, feature=Feature.TRANSACTIONS, template_id=None):
    return ImportFileRequest(
        file=FileUpload(
            filename="movements.csv",
            content_type="text/csv",
            content_length=1,
            data=BytesIO(b"x"),
        ),
        number_format=NumberFormat.ENGLISH,
        feature=feature,
        product=ProductType.ACCOUNT,
        datetime_format=None,
        date_format=None,
        template=TemplateConfig(
            id=str(template_id or uuid4()), params={"entity": "Bank"}
        ),
        preview=preview,
    )


def _build(parse_result, existing_keys=None, missing_template=False):
    position_port = AsyncMock(spec=PositionPort)
    transaction_port = AsyncMock(spec=TransactionPort)
    transaction_port.get_ref_keys.return_value = existing_keys or set()
    table_port = AsyncMock(spec=TableRWPort)
    table_port.parse.return_value = [["ref"], ["r"]]
    entity_port = AsyncMock(spec=EntityPort)
    entity_port.get_all.return_value = []
    registry = AsyncMock(spec=VirtualImportRegistry)
    registry.get_last_import_records.return_value = []
    template_port = AsyncMock(spec=TemplatePort)
    template_port.get_by_id.return_value = None if missing_template else _template()
    parser = AsyncMock(spec=TemplateParserPort)
    parser.transactions.return_value = parse_result
    handler = MagicMock()
    handler.start.return_value = AsyncMock()
    labeler = AsyncMock(spec=TransactionLabeler)
    use_case = ImportFileImpl(
        position_port,
        transaction_port,
        table_port,
        entity_port,
        registry,
        template_port,
        parser,
        handler,
        labeler,
    )
    return use_case, transaction_port, entity_port, registry, labeler


def _scenario():
    stored = _entity("Stored")
    created = _entity("Created")
    new_tx = _account_tx(stored, "new")
    duplicated_tx = _account_tx(stored, "old")
    created_tx = _account_tx(created, "old")
    crypto_tx = _crypto_tx(stored, "old")
    parse_error = ImportError(
        type=ImportErrorType.VALIDATION_ERROR,
        entry="movements.csv",
        detail=[{"field": "amount", "value": "x"}],
        row=["bad"],
    )
    result = TransactionsImportResult(
        transactions=Transactions(
            account=[new_tx, duplicated_tx, created_tx], investment=[crypto_tx]
        ),
        created_entities={created},
        errors=[parse_error],
        origins={
            duplicated_tx.id: ImportRowOrigin(entry="movements.csv", row=["old"]),
        },
    )
    existing_keys = {(stored.id, ProductType.ACCOUNT, "old")}
    return result, existing_keys, stored, created, new_tx, created_tx, crypto_tx


class TestImportFileTransactions:
    @pytest.mark.asyncio
    async def test_preview_excludes_duplicates_without_persisting(self):
        result, keys, stored, created, new_tx, created_tx, crypto_tx = _scenario()
        use_case, tx_port, entity_port, registry, labeler = _build(result, keys)

        outcome = await use_case.execute(_request(preview=True))

        assert outcome.code == ImportResultCode.COMPLETED
        tx_port.get_ref_keys.assert_awaited_once_with([stored.id])
        assert outcome.data.transactions.account == [new_tx, created_tx]
        assert outcome.data.transactions.investment == [crypto_tx]
        assert [error.type for error in outcome.errors] == [
            ImportErrorType.VALIDATION_ERROR,
            ImportErrorType.DUPLICATED,
        ]
        duplicated = outcome.errors[1]
        assert duplicated.entry == "movements.csv"
        assert duplicated.detail == [{"field": "ref", "value": "old"}]
        assert duplicated.row == ["old"]
        tx_port.save.assert_not_awaited()
        entity_port.insert.assert_not_awaited()
        registry.insert.assert_not_awaited()
        labeler.classify.assert_not_awaited()
        labeler.classify_external.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_commit_saves_only_unique_transactions(self):
        result, keys, stored, created, new_tx, created_tx, crypto_tx = _scenario()
        use_case, tx_port, entity_port, registry, labeler = _build(result, keys)

        outcome = await use_case.execute(_request(preview=False))

        assert outcome.code == ImportResultCode.COMPLETED
        entity_port.insert.assert_awaited_once_with(created)
        saved = tx_port.save.await_args.args[0]
        assert saved.account == [new_tx, created_tx]
        assert saved.investment == [crypto_tx]
        labeler.classify.assert_awaited_once()
        classified_ids = labeler.classify.await_args.args[0].ids
        assert classified_ids == [new_tx.id, created_tx.id]
        labeler.link_settlements.assert_awaited_once()
        labeler.classify_external.assert_awaited_once()
        assert labeler.classify_external.await_args.args[0].ids == [
            new_tx.id,
            created_tx.id,
        ]
        entries = registry.insert.await_args.args[0]
        assert {entry.entity_id for entry in entries} == {stored.id, created.id}
        assert all(entry.feature == Feature.TRANSACTIONS for entry in entries)

    @pytest.mark.asyncio
    async def test_reimport_of_existing_rows_saves_nothing_new(self):
        stored = _entity("Stored")
        first = _account_tx(stored, "a")
        second = _account_tx(stored, "b")
        result = TransactionsImportResult(
            transactions=Transactions(account=[first, second], investment=[]),
            created_entities=set(),
            errors=[],
        )
        keys = {
            (stored.id, ProductType.ACCOUNT, "a"),
            (stored.id, ProductType.ACCOUNT, "b"),
        }
        use_case, tx_port, _, registry, labeler = _build(result, keys)

        outcome = await use_case.execute(_request(preview=False))

        assert outcome.data.transactions.account == []
        assert [error.type for error in outcome.errors] == [
            ImportErrorType.DUPLICATED,
            ImportErrorType.DUPLICATED,
        ]
        labeler.classify.assert_not_awaited()
        labeler.classify_external.assert_not_awaited()
        registry.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_only_new_entities_query_no_existing_keys(self):
        created = _entity("Created")
        tx = _account_tx(created, "a")
        result = TransactionsImportResult(
            transactions=Transactions(account=[tx], investment=[]),
            created_entities={created},
            errors=[],
        )
        use_case, tx_port, _, _, _ = _build(result)

        outcome = await use_case.execute(_request(preview=True))

        tx_port.get_ref_keys.assert_awaited_once_with([])
        assert outcome.data.transactions.account == [tx]
        assert outcome.errors is None

    @pytest.mark.asyncio
    async def test_invalid_template_returns_error(self):
        result, keys, *_ = _scenario()
        use_case, tx_port, _, _, _ = _build(result, keys, missing_template=True)

        outcome = await use_case.execute(_request(preview=False))

        assert outcome.code == ImportResultCode.INVALID_TEMPLATE
        tx_port.get_ref_keys.assert_not_awaited()
        tx_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_imports_with_ephemeral_template_fields_without_saved_template(self):
        result, keys, _, created, new_tx, created_tx, _ = _scenario()
        use_case, tx_port, entity_port, _, _ = _build(
            result, keys, missing_template=True
        )
        req = ImportFileRequest(
            file=FileUpload(
                filename="movements.csv",
                content_type="text/csv",
                content_length=1,
                data=BytesIO(b"x"),
            ),
            number_format=NumberFormat.EUROPEAN,
            feature=Feature.TRANSACTIONS,
            product=ProductType.ACCOUNT,
            datetime_format=None,
            date_format=None,
            template=None,
            preview=False,
            template_fields=[
                TemplatedField(field="date", name="Fecha"),
                TemplatedField(field="name", name="Concepto"),
                TemplatedField(field="amount", name="Importe"),
                TemplatedField(field="currency", name="currency", default_value="EUR"),
            ],
            template_params={"entity": "Bank"},
        )

        outcome = await use_case.execute(req)

        assert outcome.code == ImportResultCode.COMPLETED
        entity_port.insert.assert_awaited_once_with(created)
        tx_port.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_incomplete_ephemeral_template_fields(self):
        result, keys, *_ = _scenario()
        use_case, tx_port, _, _, _ = _build(result, keys)
        req = ImportFileRequest(
            file=FileUpload(
                filename="movements.csv",
                content_type="text/csv",
                content_length=1,
                data=BytesIO(b"x"),
            ),
            number_format=NumberFormat.EUROPEAN,
            feature=Feature.TRANSACTIONS,
            product=ProductType.ACCOUNT,
            datetime_format=None,
            date_format=None,
            template=None,
            preview=True,
            template_fields=[TemplatedField(field="date", name="Fecha")],
            template_params={"entity": "Bank"},
        )

        outcome = await use_case.execute(req)

        assert outcome.code == ImportResultCode.INVALID_TEMPLATE
        tx_port.save.assert_not_awaited()
