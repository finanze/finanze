from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from application.ports.file_rw_port import TableRWPort
from application.ports.historic_port import HistoricPort
from application.ports.position_port import PositionPort
from application.ports.template_port import TemplatePort
from application.ports.template_processor_port import TemplateProcessorPort
from application.ports.transaction_port import TransactionPort
from application.use_cases.export_file import ExportFileImpl
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.export import FileExportRequest, FileFormat, NumberFormat
from domain.global_position import ProductType
from domain.transactions import Transactions


def _build_use_case():
    position_port = AsyncMock(spec=PositionPort)
    auto_contr_port = AsyncMock(spec=AutoContributionsPort)
    tx_port = AsyncMock(spec=TransactionPort)
    tx_port.get_all.return_value = Transactions(account=[], investment=[])
    historic_port = AsyncMock(spec=HistoricPort)
    entity_port = AsyncMock(spec=EntityPort)
    disabled = Entity(
        id=uuid4(),
        name="Disabled",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    entity_port.get_disabled_entities.return_value = [disabled]
    template_port = AsyncMock(spec=TemplatePort)
    processor = AsyncMock(spec=TemplateProcessorPort)
    processor.process.return_value = [["ref", "name"], ["r1", "Coffee"]]
    table_rw = AsyncMock(spec=TableRWPort)
    table_rw.convert.return_value = b"ref,name\nr1,Coffee\n"
    uc = ExportFileImpl(
        position_port=position_port,
        auto_contr_port=auto_contr_port,
        transaction_port=tx_port,
        historic_port=historic_port,
        entity_port=entity_port,
        template_port=template_port,
        template_processor=processor,
        table_rw_port=table_rw,
    )
    return uc, tx_port, disabled


class TestExportFileTransactionsDateRange:
    @pytest.mark.asyncio
    async def test_forwards_date_range_and_products_to_transaction_port(self):
        uc, tx_port, disabled = _build_use_case()
        req = FileExportRequest(
            format=FileFormat.CSV,
            number_format=NumberFormat.EUROPEAN,
            feature=Feature.TRANSACTIONS,
            data=[ProductType.ACCOUNT],
            from_date=date(2026, 1, 1),
            to_date=date(2026, 3, 31),
        )

        result = await uc.execute(req)

        tx_port.get_all.assert_awaited_once_with(
            excluded_entities=[disabled.id],
            from_date=date(2026, 1, 1),
            to_date=date(2026, 3, 31),
            product_types=[ProductType.ACCOUNT],
        )
        assert result.filename.startswith("export_transactions_2026-01-01_2026-03-31_")
        assert result.filename.endswith(".csv")

    @pytest.mark.parametrize(
        "from_date,to_date,expected_prefix",
        [
            (None, None, "export_transactions_20"),
            (date(2026, 5, 1), None, "export_transactions_from_2026-05-01_"),
            (None, date(2026, 5, 31), "export_transactions_until_2026-05-31_"),
        ],
    )
    @pytest.mark.asyncio
    async def test_formats_filename_for_open_and_unbounded_ranges(
        self, from_date, to_date, expected_prefix
    ):
        uc, tx_port, disabled = _build_use_case()
        req = FileExportRequest(
            format=FileFormat.TSV,
            number_format=NumberFormat.ENGLISH,
            feature=Feature.TRANSACTIONS,
            data=None,
            from_date=from_date,
            to_date=to_date,
        )

        result = await uc.execute(req)

        tx_port.get_all.assert_awaited_once_with(
            excluded_entities=[disabled.id],
            from_date=from_date,
            to_date=to_date,
            product_types=None,
        )
        assert result.filename.startswith(expected_prefix)
        assert result.filename.endswith(".tsv")
