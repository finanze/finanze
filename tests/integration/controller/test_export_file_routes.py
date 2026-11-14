import csv
import io
import sqlite3
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import openpyxl
import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.use_cases.export_file import ExportFileImpl
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.export import FileFormat
from domain.fetch_record import DataSource
from domain.global_position import Deposit, Deposits, GlobalPosition, ProductType
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType
from domain.transactions import AccountTx, StockTx, Transactions, TxType
from domain.virtual_data import VirtualDataImport, VirtualDataSource
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.export_file import export_file
from infrastructure.repository import (
    AutoContributionsRepository,
    EntityRepository,
    HistoricRepository,
    PositionRepository,
    TransactionRepository,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.templates.template_repository import TemplateRepository
from infrastructure.repository.virtual.virtual_import_repository import (
    VirtualImportRepository,
)
from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
from infrastructure.templating.templated_data_generator import TemplatedDataGenerator

EXPORT_URL = "/api/v1/data/export/file"


@pytest_asyncio.fixture
async def export_ctx(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    db_client = DBClient(connection)
    await DatabaseUpgrader(
        db_client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()

    entity_repo = EntityRepository(client=db_client)
    position_repo = PositionRepository(client=db_client)
    template_repo = TemplateRepository(client=db_client)
    tx_repo = TransactionRepository(client=db_client)
    csv_adapter = CSVFileTableAdapter()
    table_rw = TableRWDispatcher(
        {
            FileFormat.CSV: csv_adapter,
            FileFormat.TSV: csv_adapter,
            FileFormat.XLSX: XLSXFileTableAdapter(),
        }
    )
    export_uc = ExportFileImpl(
        position_port=position_repo,
        auto_contr_port=AutoContributionsRepository(client=db_client),
        transaction_port=tx_repo,
        historic_port=HistoricRepository(client=db_client),
        entity_port=entity_repo,
        template_port=template_repo,
        template_processor=TemplatedDataGenerator(),
        table_rw_port=table_rw,
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route(EXPORT_URL, methods=["POST"])
    async def export_handler():
        return await export_file(export_uc)

    bank = Entity(
        id=uuid4(),
        name="Export Bank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )
    await entity_repo.insert(bank)
    manual_import_id = uuid4()
    await VirtualImportRepository(client=db_client).insert(
        [
            VirtualDataImport(
                import_id=manual_import_id,
                global_position_id=None,
                source=VirtualDataSource.MANUAL,
                date=datetime(2026, 3, 2, 10, 0, tzinfo=tzlocal()),
                feature=Feature.TRANSACTIONS,
                entity_id=bank.id,
            )
        ]
    )
    await tx_repo.save(
        Transactions(
            account=[
                AccountTx(
                    id=uuid4(),
                    ref="jan-tx",
                    name="January Salary",
                    amount=Dezimal(2000),
                    currency="EUR",
                    type=TxType.INFLOW,
                    date=datetime(2026, 1, 15, 9, 0, tzinfo=tzlocal()),
                    entity=bank,
                    source=DataSource.MANUAL,
                    product_type=ProductType.ACCOUNT,
                    fees=Dezimal(0),
                    retentions=Dezimal(0),
                ),
                AccountTx(
                    id=uuid4(),
                    ref="feb-end-tx",
                    name="End of Feb Dinner",
                    amount=Dezimal("45.75"),
                    currency="EUR",
                    type=TxType.OUTFLOW,
                    date=datetime(2026, 2, 28, 23, 45, tzinfo=tzlocal()),
                    entity=bank,
                    source=DataSource.MANUAL,
                    product_type=ProductType.ACCOUNT,
                    fees=Dezimal(0),
                    retentions=Dezimal(0),
                ),
                AccountTx(
                    id=uuid4(),
                    ref="mar-tx",
                    name="March Rent",
                    amount=Dezimal(900),
                    currency="EUR",
                    type=TxType.OUTFLOW,
                    date=datetime(2026, 3, 2, 8, 0, tzinfo=tzlocal()),
                    entity=bank,
                    source=DataSource.MANUAL,
                    product_type=ProductType.ACCOUNT,
                    fees=Dezimal(0),
                    retentions=Dezimal(0),
                ),
            ],
            investment=[
                StockTx(
                    id=uuid4(),
                    ref="feb-stk",
                    name="ETF Buy",
                    amount=Dezimal(500),
                    currency="EUR",
                    type=TxType.BUY,
                    date=datetime(2026, 2, 10, 12, 0, tzinfo=tzlocal()),
                    entity=bank,
                    source=DataSource.MANUAL,
                    product_type=ProductType.STOCK_ETF,
                    isin="IE00B4L5Y983",
                    ticker="IWDA",
                    shares=Dezimal(5),
                    price=Dezimal(100),
                    fees=Dezimal(0),
                    retentions=Dezimal(0),
                )
            ],
        )
    )

    deposit_creation = datetime(2026, 2, 5, 14, 30, 0, tzinfo=timezone.utc)
    gp_id = uuid4()
    await position_repo.save(
        GlobalPosition(
            id=gp_id,
            entity=bank,
            date=datetime(2026, 3, 2, 10, 0, tzinfo=tzlocal()),
            source=DataSource.MANUAL,
            products={
                ProductType.DEPOSIT: Deposits(
                    [
                        Deposit(
                            id=uuid4(),
                            name="Fixed Deposit 12M",
                            amount=Dezimal("1250.50"),
                            currency="EUR",
                            interest_rate=Dezimal("0.035"),
                            creation=deposit_creation,
                            maturity=date(2027, 2, 5),
                            source=DataSource.MANUAL,
                        )
                    ]
                )
            },
        )
    )
    await VirtualImportRepository(client=db_client).insert(
        [
            VirtualDataImport(
                import_id=manual_import_id,
                global_position_id=gp_id,
                source=VirtualDataSource.MANUAL,
                date=datetime(2026, 3, 2, 10, 0, tzinfo=tzlocal()),
                feature=Feature.POSITION,
                entity_id=bank.id,
            )
        ]
    )

    tx_template_id = uuid4()
    await template_repo.save(
        Template(
            id=tx_template_id,
            name="Compact Account Export",
            feature=Feature.TRANSACTIONS,
            type=TemplateType.EXPORT,
            products=[ProductType.ACCOUNT],
            fields=[
                TemplatedField(field="date", name="Movement Date"),
                TemplatedField(field="name", name="Concept"),
                TemplatedField(field="amount", name="Total"),
            ],
        )
    )
    app.tx_template_id = str(tx_template_id)
    app.deposit_creation_local = deposit_creation.astimezone(tzlocal())

    yield app.test_client()
    connection.close()


def _csv_rows(raw_bytes: bytes, delimiter: str = ",") -> list[dict[str, str]]:
    text = raw_bytes.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


class TestExportFileRouteDateRange:
    @pytest.mark.asyncio
    async def test_exports_only_transactions_within_date_range_and_selected_products(
        self, export_ctx
    ):
        resp = await export_ctx.post(
            EXPORT_URL,
            json={
                "format": "CSV",
                "number_format": "EUROPEAN",
                "feature": "TRANSACTIONS",
                "data": ["ACCOUNT"],
                "from_date": "2026-02-01",
                "to_date": "2026-02-28",
            },
        )

        assert resp.status_code == 200
        disposition = resp.headers.get("Content-Disposition", "")
        assert "export_transactions_2026-02-01_2026-02-28_" in disposition
        rows = _csv_rows(await resp.get_data())
        assert [row["ref"] for row in rows] == ["feb-end-tx"]
        assert rows[0]["amount"] == "45,75"

    @pytest.mark.parametrize(
        "payload",
        [
            {
                "format": "CSV",
                "number_format": "EUROPEAN",
                "feature": "TRANSACTIONS",
                "data": ["ACCOUNT"],
                "from_date": "2026-03-10",
                "to_date": "2026-02-01",
            },
            {
                "format": "CSV",
                "number_format": "EUROPEAN",
                "feature": "TRANSACTIONS",
                "data": ["ACCOUNT"],
                "from_date": "15/02/2026",
            },
            {
                "format": "CSV",
                "number_format": "EUROPEAN",
                "feature": "POSITION",
                "data": ["ACCOUNT"],
                "from_date": "2026-02-01",
            },
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_invalid_date_ranges(self, export_ctx, payload):
        resp = await export_ctx.post(EXPORT_URL, json=payload)

        assert resp.status_code == 400
        assert (await resp.get_json())["code"] == "INVALID_REQUEST"


class TestExportFileRouteFormatsAndTemplates:
    @pytest.mark.asyncio
    async def test_applies_independent_date_and_datetime_formats_and_iso_defaults(
        self, export_ctx
    ):
        default_resp = await export_ctx.post(
            EXPORT_URL,
            json={
                "format": "CSV",
                "number_format": "ENGLISH",
                "feature": "POSITION",
                "data": ["DEPOSIT"],
            },
        )
        assert default_resp.status_code == 200
        default_rows = _csv_rows(await default_resp.get_data())
        assert len(default_rows) == 1
        assert default_rows[0]["maturity"] == "2027-02-05"
        assert "T" in default_rows[0]["creation"]
        assert default_rows[0]["amount"] == "1250.50"

        formatted_resp = await export_ctx.post(
            EXPORT_URL,
            json={
                "format": "TSV",
                "number_format": "EUROPEAN",
                "feature": "POSITION",
                "data": ["DEPOSIT"],
                "date_format": "%d/%m/%Y",
                "datetime_format": "%d-%m-%Y %H:%M:%S",
            },
        )
        assert formatted_resp.status_code == 200
        assert "text/tab-separated-values" in formatted_resp.headers["Content-Type"]
        tsv_rows = _csv_rows(await formatted_resp.get_data(), delimiter="\t")
        assert len(tsv_rows) == 1
        assert tsv_rows[0]["maturity"] == "05/02/2027"
        assert tsv_rows[0][
            "creation"
        ] == export_ctx.app.deposit_creation_local.strftime("%d-%m-%Y %H:%M:%S")
        assert tsv_rows[0]["amount"] == "1250,50"

    @pytest.mark.asyncio
    async def test_exports_xlsx_with_template_and_custom_datetime_format(
        self, export_ctx
    ):
        resp = await export_ctx.post(
            EXPORT_URL,
            json={
                "format": "XLSX",
                "number_format": "ENGLISH",
                "feature": "TRANSACTIONS",
                "data": ["ACCOUNT"],
                "from_date": "2026-02-01",
                "to_date": "2026-02-28",
                "datetime_format": "%Y/%m/%d %H:%M",
                "template": {"id": export_ctx.app.tx_template_id},
            },
        )

        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        wb = openpyxl.load_workbook(io.BytesIO(await resp.get_data()), data_only=True)
        sheet = wb.active
        values = list(sheet.iter_rows(values_only=True))
        assert values[0] == ("Movement Date", "Concept", "Total")
        assert len(values) == 2
        assert values[1][1] == "End of Feb Dinner"
        assert str(values[1][2]) == "45.75"
        assert values[1][0] == "2026/02/28 23:45"
