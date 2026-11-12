from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.position_port import PositionPort
from application.ports.sheets_port import SheetsPort
from application.ports.template_parser_port import TemplateParserPort
from application.ports.template_port import TemplatePort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.import_sheets import ImportSheetsImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.importing import (
    ImportErrorType,
    ImportResultCode,
    ImportRowOrigin,
    PositionImportResult,
    TransactionsImportResult,
)
from domain.settings import (
    ImportConfig,
    ImportTransactionsSheetConfig,
    SheetsGlobalConfig,
    SheetsImportConfig,
    TemplateConfig,
)
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType
from domain.transactions import AccountTx, Transactions, TxType


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
        source=DataSource.SHEETS,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=Dezimal(10),
    )


def _sheets_config(params):
    return SheetsImportConfig(
        globals=SheetsGlobalConfig(spreadsheetId="spreadsheet"),
        position=None,
        transactions=[
            ImportTransactionsSheetConfig(
                range="Movements",
                template=TemplateConfig(id=str(uuid4()), params=params),
                data=ProductType.ACCOUNT.value,
            )
        ],
    )


def _build(parse_result, existing_keys=None, params=None):
    position_port = AsyncMock(spec=PositionPort)
    transaction_port = AsyncMock(spec=TransactionPort)
    transaction_port.get_ref_keys.return_value = existing_keys or set()
    sheets_port = AsyncMock(spec=SheetsPort)
    sheets_port.read.return_value = [["ref"], ["r"]]
    entity_port = AsyncMock(spec=EntityPort)
    entity_port.get_all.return_value = []
    integration_port = AsyncMock(spec=ExternalIntegrationPort)
    integration_port.get_payload.return_value = {"token": "x"}
    config_port = AsyncMock(spec=ConfigPort)
    config_port.load_sections.return_value = MagicMock(
        importing=ImportConfig(sheets=_sheets_config(params))
    )
    registry = AsyncMock(spec=VirtualImportRegistry)
    template_port = AsyncMock(spec=TemplatePort)
    template_port.get_by_id.return_value = Template(
        id=uuid4(),
        name="Import",
        feature=Feature.TRANSACTIONS,
        type=TemplateType.IMPORT,
        fields=[TemplatedField(field="ref", name="ref")],
        products=[ProductType.ACCOUNT],
    )
    parser = AsyncMock(spec=TemplateParserPort)
    parser.global_positions.return_value = PositionImportResult(
        positions=[], created_entities=set(), errors=[]
    )
    parser.transactions.return_value = parse_result
    handler = MagicMock()
    handler.start.return_value = AsyncMock()
    label_port = AsyncMock(spec=TransactionLabelPort)
    label_port.get_classifications_by_source.return_value = {}
    labeler = AsyncMock(spec=TransactionLabeler)
    use_case = ImportSheetsImpl(
        position_port,
        transaction_port,
        sheets_port,
        entity_port,
        integration_port,
        config_port,
        registry,
        template_port,
        parser,
        handler,
        label_port,
        labeler,
    )
    return use_case, transaction_port, parser, labeler


class TestImportSheetsTransactions:
    @pytest.mark.asyncio
    async def test_forwards_template_params_to_parser(self):
        result = TransactionsImportResult(
            transactions=Transactions(account=[], investment=[]),
            created_entities=set(),
            errors=[],
        )
        use_case, _, parser, _ = _build(result, params={"entity": "My Bank"})

        await use_case.execute()

        candidates = parser.transactions.await_args.args[0]
        assert len(candidates) == 1
        assert candidates[0].name == "Movements"
        assert candidates[0].source == DataSource.SHEETS
        assert candidates[0].params.product == ProductType.ACCOUNT
        assert candidates[0].params.params == {"entity": "My Bank"}

    @pytest.mark.asyncio
    async def test_missing_template_params_default_to_empty(self):
        result = TransactionsImportResult(
            transactions=Transactions(account=[], investment=[]),
            created_entities=set(),
            errors=[],
        )
        use_case, _, parser, _ = _build(result, params=None)

        await use_case.execute()

        candidates = parser.transactions.await_args.args[0]
        assert candidates[0].params.params == {}

    @pytest.mark.asyncio
    async def test_dedupes_against_non_sheets_data_after_cleanup(self):
        stored = _entity("Stored")
        new_tx = _account_tx(stored, "new")
        manual_dup = _account_tx(stored, "manual")
        result = TransactionsImportResult(
            transactions=Transactions(account=[new_tx, manual_dup], investment=[]),
            created_entities=set(),
            errors=[],
            origins={manual_dup.id: ImportRowOrigin(entry="Movements", row=["m"])},
        )
        keys = {(stored.id, ProductType.ACCOUNT, "manual")}
        use_case, tx_port, _, labeler = _build(
            result, existing_keys=keys, params={"entity": "Stored"}
        )

        outcome = await use_case.execute()

        assert outcome.code == ImportResultCode.COMPLETED
        call_order = [call[0] for call in tx_port.mock_calls]
        assert call_order == ["delete_by_source", "get_ref_keys", "save"]
        tx_port.delete_by_source.assert_awaited_once_with(DataSource.SHEETS)
        tx_port.get_ref_keys.assert_awaited_once_with([stored.id])
        saved = tx_port.save.await_args.args[0]
        assert saved.account == [new_tx]
        assert outcome.data.transactions.account == [new_tx]
        assert [error.type for error in outcome.errors] == [ImportErrorType.DUPLICATED]
        assert outcome.errors[0].entry == "Movements"
        assert outcome.errors[0].row == ["m"]
        assert labeler.classify.await_args.args[0].ids == [new_tx.id]
