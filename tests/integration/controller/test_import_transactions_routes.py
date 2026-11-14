import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from werkzeug.datastructures import FileStorage

from application.use_cases.get_transactions import GetTransactionsImpl
from application.use_cases.import_file import ImportFileImpl
from application.use_cases.import_sheets import ImportSheetsImpl
from domain.data_init import DatasourceInitContext
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.export import FileFormat
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.settings import (
    AssetConfig,
    CryptoAssetConfig,
    ImportConfig,
    ImportTransactionsSheetConfig,
    Settings,
    SheetsGlobalConfig,
    SheetsImportConfig,
    TemplateConfig,
)
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    FundPortfolioTx,
    Transactions,
    TxType,
)
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.import_file import import_file_route
from infrastructure.controller.routes.import_sheets import import_sheets
from infrastructure.controller.routes.transactions import transactions
from infrastructure.labeling.transaction_labeler_adapter import (
    TransactionLabelerAdapter,
)
from infrastructure.repository import (
    EntityRepository,
    PositionRepository,
    TransactionRepository,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.labeling.label_repository import LabelRepository
from infrastructure.repository.labeling.labeling_rule_repository import (
    LabelingRuleRepository,
)
from infrastructure.repository.labeling.transaction_label_repository import (
    TransactionLabelRepository,
)
from infrastructure.repository.templates.template_repository import TemplateRepository
from infrastructure.repository.virtual.virtual_import_repository import (
    VirtualImportRepository,
)
from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
from infrastructure.table.html_file_table_adapter import HTMLFileTableAdapter
from infrastructure.table.pdf_file_table_adapter import PDFFileTableAdapter
from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
from infrastructure.templating.templated_data_parser import TemplateDataParser

RESOURCES = Path(__file__).resolve().parents[2] / "resources" / "import"

IMPORT_URL = "/api/v1/import/file"
SHEETS_URL = "/api/v1/import/sheets"
TXS_URL = "/api/v1/transactions?limit=100"

ACCOUNT_HEADERS = [
    "ref",
    "name",
    "amount",
    "currency",
    "type",
    "date",
    "fees",
    "counterparty",
    "iban",
]
CRYPTO_HEADERS = [
    "ref",
    "name",
    "amount",
    "currency",
    "type",
    "date",
    "symbol",
    "currency_amount",
    "price",
    "fees",
]
PORTFOLIO_HEADERS = [
    "ref",
    "name",
    "amount",
    "currency",
    "type",
    "date",
    "portfolio_name",
    "iban",
]


def _csv(*rows):
    return "\n".join(",".join(row) for row in rows).encode("utf-8")


class _Ctx:
    def __init__(self, http, tx_repo, entity_repo, template_repo, sheets_port):
        self.http = http
        self.tx_repo = tx_repo
        self.entity_repo = entity_repo
        self.template_repo = template_repo
        self.sheets_port = sheets_port
        self.sheets_config = None

    async def template(self, product, headers, fields=None):
        template = Template(
            id=uuid4(),
            name=f"{product.value} import {uuid4()}",
            feature=Feature.TRANSACTIONS,
            type=TemplateType.IMPORT,
            fields=fields
            or [TemplatedField(field=header, name=header) for header in headers],
            products=[product],
        )
        await self.template_repo.save(template)
        return template

    async def entity(self, name, entity_type=EntityType.FINANCIAL_INSTITUTION):
        entity = Entity(
            id=uuid4(),
            name=name,
            natural_id=None,
            type=entity_type,
            origin=EntityOrigin.MANUAL,
            icon_url=None,
        )
        await self.entity_repo.insert(entity)
        return entity

    async def import_file(
        self,
        template,
        product,
        content,
        entity="Import Bank",
        preview=False,
        filename="movements.csv",
        content_type="text/csv",
    ):
        form = {
            "feature": "TRANSACTIONS",
            "product": product.value,
            "numberFormat": "ENGLISH",
            "templateId": str(template.id),
            "templateParams": f'{{"entity": "{entity}"}}',
        }
        response = await self.http.post(
            f"{IMPORT_URL}?preview={'true' if preview else 'false'}",
            form=form,
            files={
                "file": FileStorage(
                    stream=io.BytesIO(content),
                    filename=filename,
                    content_type=content_type,
                )
            },
        )
        assert response.status_code == 200
        return await response.get_json()

    async def txs(self):
        response = await self.http.get(TXS_URL)
        assert response.status_code == 200
        return (await response.get_json())["transactions"]


@pytest_asyncio.fixture
async def ctx(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()

    tx_repo = TransactionRepository(client=client)
    entity_repo = EntityRepository(client=client)
    position_repo = PositionRepository(client=client)
    template_repo = TemplateRepository(client=client)
    virtual_repo = VirtualImportRepository(client=client)
    tx_label_repo = TransactionLabelRepository(client)
    handler = TransactionHandler(client)

    config_port = AsyncMock()
    config_port.load_sections = AsyncMock(
        return_value=Settings(
            lastUpdate=datetime.now(tzlocal()).isoformat(),
            assets=AssetConfig(crypto=CryptoAssetConfig()),
        )
    )
    labeler = TransactionLabelerAdapter(
        transaction_port=tx_repo,
        transaction_label_port=tx_label_repo,
        labeling_rule_port=LabelingRuleRepository(client),
        label_port=LabelRepository(client),
        config_port=config_port,
        external_integration_port=AsyncMock(),
        providers={},
        transaction_handler_port=handler,
    )
    csv_adapter = CSVFileTableAdapter()
    table_rw = TableRWDispatcher(
        {
            FileFormat.CSV: csv_adapter,
            FileFormat.TSV: csv_adapter,
            FileFormat.XLSX: XLSXFileTableAdapter(),
            FileFormat.HTML: HTMLFileTableAdapter(),
            FileFormat.PDF: PDFFileTableAdapter(),
        }
    )
    parser = TemplateDataParser()

    import_file_uc = ImportFileImpl(
        position_port=position_repo,
        transaction_port=tx_repo,
        table_rw_port=table_rw,
        entity_port=entity_repo,
        virtual_import_registry=virtual_repo,
        template_port=template_repo,
        template_parser=parser,
        transaction_handler_port=handler,
        transaction_labeler=labeler,
    )

    sheets_port = AsyncMock()
    integration_port = AsyncMock()
    integration_port.get_payload = AsyncMock(return_value={"token": "x"})
    sheets_config_port = AsyncMock()
    import_sheets_uc = ImportSheetsImpl(
        position_repo,
        tx_repo,
        sheets_port,
        entity_repo,
        integration_port,
        sheets_config_port,
        virtual_repo,
        template_repo,
        parser,
        handler,
        tx_label_repo,
        labeler,
    )

    enabled_entities = AsyncMock()
    enabled_entities.get_disabled_entities = AsyncMock(return_value=[])
    get_transactions_uc = GetTransactionsImpl(tx_repo, enabled_entities)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route(IMPORT_URL, methods=["POST"])
    async def import_file_handler():
        return await import_file_route(import_file_uc)

    @app.route(SHEETS_URL, methods=["POST"])
    async def import_sheets_handler():
        return await import_sheets(import_sheets_uc)

    @app.route("/api/v1/transactions", methods=["GET"])
    async def transactions_handler():
        return await transactions(get_transactions_uc)

    context = _Ctx(app.test_client(), tx_repo, entity_repo, template_repo, sheets_port)

    def configure_sheets(template, entity):
        sheets_config_port.load_sections = AsyncMock(
            return_value=MagicMock(
                importing=ImportConfig(
                    sheets=SheetsImportConfig(
                        globals=SheetsGlobalConfig(
                            spreadsheetId="spreadsheet",
                            datetimeFormat="%Y-%m-%dT%H:%M:%S",
                        ),
                        transactions=[
                            ImportTransactionsSheetConfig(
                                range="Movements",
                                template=TemplateConfig(
                                    id=str(template.id), params={"entity": entity}
                                ),
                                data=ProductType.ACCOUNT.value,
                            )
                        ],
                    )
                )
            )
        )

    context.configure_sheets = configure_sheets
    yield context
    connection.close()


def _by_ref(txs):
    return {tx["ref"]: tx for tx in txs}


def _error_types(payload):
    return [error["type"] for error in payload.get("errors") or []]


class TestAccountFileImport:
    @pytest.mark.asyncio
    async def test_preview_returns_parsed_rows_without_persisting(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        content = _csv(
            ACCOUNT_HEADERS,
            ["a1", "Salary", "2500", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["a2", "Rent", "-900", "EUR", "", "2025-03-02T09:00:00", "", "", ""],
        )

        payload = await ctx.import_file(
            template, ProductType.ACCOUNT, content, preview=True
        )

        assert payload["code"] == "COMPLETED"
        assert "errors" not in payload
        preview = _by_ref(payload["data"]["transactions"]["account"])
        assert preview["a1"]["type"] == "INFLOW"
        assert preview["a2"]["type"] == "OUTFLOW"
        assert preview["a2"]["amount"] == 900.0
        assert await ctx.txs() == []
        assert await ctx.entity_repo.get_by_name("Import Bank") is None

    @pytest.mark.asyncio
    async def test_commit_persists_movements_and_creates_entity(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        content = _csv(
            ACCOUNT_HEADERS,
            [
                "a1",
                "Salary",
                "2500",
                "EUR",
                "",
                "2025-03-01T09:00:00",
                "",
                "ACME",
                "es91 2100 0418 4502 0005 1332",
            ],
            ["a2", "Rent", "-900.5", "EUR", "", "2025-03-02T09:00:00", "1", "", ""],
            ["a3", "Bank fee", "-3", "EUR", "FEE", "2025-03-03T09:00:00", "", "", ""],
        )

        payload = await ctx.import_file(template, ProductType.ACCOUNT, content)

        assert payload["code"] == "COMPLETED"
        assert "errors" not in payload
        stored = _by_ref(await ctx.txs())
        assert set(stored) == {"a1", "a2", "a3"}
        assert stored["a1"]["type"] == "INFLOW"
        assert stored["a1"]["amount"] == 2500.0
        assert stored["a1"]["counterparty"] == "ACME"
        assert stored["a1"]["iban"] == "ES9121000418450200051332"
        assert stored["a1"]["product_type"] == "ACCOUNT"
        assert stored["a1"]["source"] == "MANUAL"
        assert stored["a2"]["type"] == "OUTFLOW"
        assert stored["a2"]["amount"] == 900.5
        assert stored["a2"]["net_amount"] == 901.5
        assert stored["a3"]["type"] == "FEE"
        assert stored["a3"]["amount"] == 3.0
        entity = await ctx.entity_repo.get_by_name("Import Bank")
        assert entity is not None
        assert entity.type == EntityType.FINANCIAL_INSTITUTION
        assert entity.origin == EntityOrigin.MANUAL

    @pytest.mark.asyncio
    async def test_reimport_skips_existing_refs(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        first = _csv(
            ACCOUNT_HEADERS,
            ["a1", "Salary", "2500", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["a2", "Rent", "-900", "EUR", "", "2025-03-02T09:00:00", "", "", ""],
        )
        await ctx.import_file(template, ProductType.ACCOUNT, first)

        second = _csv(
            ACCOUNT_HEADERS,
            ["a1", "Salary", "2500", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["a3", "Groceries", "-60", "EUR", "", "2025-03-05T09:00:00", "", "", ""],
        )
        preview = await ctx.import_file(
            template, ProductType.ACCOUNT, second, preview=True
        )
        payload = await ctx.import_file(template, ProductType.ACCOUNT, second)

        for result in (preview, payload):
            assert [tx["ref"] for tx in result["data"]["transactions"]["account"]] == [
                "a3"
            ]
            assert _error_types(result) == ["DUPLICATED"]
            assert result["errors"][0]["entry"] == "movements.csv"
            assert result["errors"][0]["detail"] == [{"field": "ref", "value": "a1"}]
            assert result["errors"][0]["row"][0] == "a1"
        assert sorted(_by_ref(await ctx.txs())) == ["a1", "a2", "a3"]

    @pytest.mark.asyncio
    async def test_same_ref_repeated_in_file_is_imported_once(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        content = _csv(
            ACCOUNT_HEADERS,
            ["dup", "First", "10", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["dup", "Second", "20", "EUR", "", "2025-03-02T09:00:00", "", "", ""],
        )

        payload = await ctx.import_file(template, ProductType.ACCOUNT, content)

        assert _error_types(payload) == ["DUPLICATED"]
        stored = await ctx.txs()
        assert [(tx["ref"], tx["name"]) for tx in stored] == [("dup", "First")]

    @pytest.mark.asyncio
    async def test_existing_ref_on_other_entity_is_not_a_duplicate(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        content = _csv(
            ACCOUNT_HEADERS,
            ["shared", "Salary", "10", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
        )
        await ctx.import_file(template, ProductType.ACCOUNT, content, entity="Bank A")

        payload = await ctx.import_file(
            template, ProductType.ACCOUNT, content, entity="Bank B"
        )

        assert "errors" not in payload
        assert len(await ctx.txs()) == 2

    @pytest.mark.asyncio
    async def test_invalid_rows_are_reported_and_valid_rows_imported(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        content = _csv(
            ACCOUNT_HEADERS,
            ["ok", "Salary", "10", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["bad-iban", "X", "10", "EUR", "", "2025-03-01T09:00:00", "", "", "ES#1"],
            ["bad-type", "X", "10", "EUR", "BUY", "2025-03-01T09:00:00", "", "", ""],
            ["zero", "X", "0", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["no-name", "", "10", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ["bad-date", "X", "10", "EUR", "", "yesterday", "", "", ""],
            ["bad-amount", "X", "ten", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
        )

        payload = await ctx.import_file(template, ProductType.ACCOUNT, content)

        assert payload["code"] == "COMPLETED"
        errors = {error["row"][0]: error for error in payload["errors"]}
        assert errors["bad-iban"]["type"] == "VALIDATION_ERROR"
        assert errors["bad-iban"]["detail"] == [{"field": "iban", "value": "ES#1"}]
        assert errors["bad-type"]["type"] == "VALIDATION_ERROR"
        assert errors["bad-type"]["detail"] == [{"field": "type", "value": "BUY"}]
        assert errors["zero"]["type"] == "MISSING_FIELD"
        assert errors["zero"]["detail"] == ["type"]
        assert errors["no-name"]["type"] == "MISSING_FIELD"
        assert errors["no-name"]["detail"] == [{"field": "name"}]
        assert errors["bad-date"]["type"] == "VALIDATION_ERROR"
        assert errors["bad-amount"]["type"] == "VALIDATION_ERROR"
        assert len(payload["errors"]) == 6
        assert [tx["ref"] for tx in await ctx.txs()] == ["ok"]

    @pytest.mark.asyncio
    async def test_unsupported_file_is_rejected(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)

        payload = await ctx.import_file(
            template,
            ProductType.ACCOUNT,
            b"x",
            filename="movements.pdf",
            content_type="application/pdf",
        )

        assert payload["code"] == "UNSUPPORTED_FILE_FORMAT"
        assert await ctx.txs() == []


BANK_FIELDS = [
    TemplatedField(field="date", name="Fecha operación"),
    TemplatedField(field="name", name="Concepto"),
    TemplatedField(field="amount", name="Importe"),
    TemplatedField(field="currency", name="Divisa", default_value="EUR"),
]


class TestBankFileImport:
    @pytest.mark.asyncio
    async def test_legacy_xls_export_is_imported_once(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, [], BANK_FIELDS)
        content = (RESOURCES / "bank_movements.xls").read_bytes()

        async def import_xls():
            return await ctx.import_file(
                template,
                ProductType.ACCOUNT,
                content,
                filename="movements.xls",
                content_type="application/vnd.ms-excel",
            )

        first = await import_xls()
        second = await import_xls()

        assert first["code"] == "COMPLETED"
        assert _error_types(first) == ["UNEXPECTED_COLUMN"]
        assert first["errors"][0]["detail"] == ["Saldo"]
        stored = sorted(await ctx.txs(), key=lambda tx: tx["date"])
        assert [(tx["name"], tx["amount"], tx["type"]) for tx in stored] == [
            ("Nómina enero", 1500.0, "INFLOW"),
            ("Compra supermercado", 45.3, "OUTFLOW"),
            ("Recibo luz", 60.25, "OUTFLOW"),
        ]
        assert all(tx["ref"] and tx["currency"] == "EUR" for tx in stored)
        assert stored[0]["date"].startswith("2025-01-02")
        assert _error_types(second).count("DUPLICATED") == 3
        assert len(await ctx.txs()) == 3

    @pytest.mark.asyncio
    async def test_semicolon_csv_with_preamble_and_local_formats(self, ctx):
        template = await ctx.template(ProductType.ACCOUNT, [], BANK_FIELDS)
        content = (
            "Cuenta;ES9121000418450200051332\n"
            "Periodo;01/01/2025 - 31/01/2025\n"
            "\n"
            "Fecha operación;Concepto;Importe;Divisa\n"
            "31/01/2025;Nómina;1.500,00;EUR\n"
            "15/01/2025;Hotel;-120,50;USD\n"
        ).encode("cp1252")

        payload = await ctx.import_file(template, ProductType.ACCOUNT, content)

        assert payload["code"] == "COMPLETED"
        assert "errors" not in payload
        stored = {tx["name"]: tx for tx in await ctx.txs()}
        assert stored["Nómina"]["amount"] == 1500.0
        assert stored["Nómina"]["date"].startswith("2025-01-31")
        assert stored["Hotel"]["amount"] == 120.5
        assert stored["Hotel"]["currency"] == "USD"
        assert stored["Hotel"]["type"] == "OUTFLOW"


class TestInvestmentFileImport:
    @pytest.mark.asyncio
    async def test_crypto_import_into_existing_exchange(self, ctx):
        exchange = await ctx.entity("My Exchange", EntityType.CRYPTO_EXCHANGE)
        template = await ctx.template(ProductType.CRYPTO, CRYPTO_HEADERS)
        content = _csv(
            CRYPTO_HEADERS,
            [
                "c1",
                "Bitcoin",
                "500",
                "EUR",
                "BUY",
                "2025-03-01T09:00:00",
                "btc",
                "0.005",
                "100000",
                "1.5",
            ],
            [
                "c2",
                "Bitcoin",
                "-300",
                "EUR",
                "SELL",
                "2025-03-04T09:00:00",
                "BTC",
                "-0.003",
                "100000",
                "",
            ],
        )

        payload = await ctx.import_file(
            template, ProductType.CRYPTO, content, entity="My Exchange"
        )

        assert "errors" not in payload
        stored = _by_ref(await ctx.txs())
        assert stored["c1"]["product_type"] == "CRYPTO"
        assert stored["c1"]["symbol"] == "BTC"
        assert stored["c1"]["net_amount"] == 501.5
        assert stored["c1"]["entity"]["id"] == str(exchange.id)
        assert stored["c2"]["type"] == "SELL"
        assert stored["c2"]["amount"] == 300.0
        assert stored["c2"]["currency_amount"] == 0.003

        again = await ctx.import_file(
            template, ProductType.CRYPTO, content, entity="My Exchange"
        )
        assert _error_types(again) == ["DUPLICATED", "DUPLICATED"]
        assert len(await ctx.txs()) == 2

    @pytest.mark.asyncio
    async def test_crypto_rejects_account_types_and_missing_symbol(self, ctx):
        template = await ctx.template(ProductType.CRYPTO, CRYPTO_HEADERS)
        content = _csv(
            CRYPTO_HEADERS,
            [
                "c1",
                "Bitcoin",
                "500",
                "EUR",
                "INFLOW",
                "2025-03-01T09:00:00",
                "BTC",
                "0.005",
                "100000",
                "",
            ],
            [
                "c2",
                "Bitcoin",
                "500",
                "EUR",
                "BUY",
                "2025-03-01T09:00:00",
                "",
                "0.005",
                "100000",
                "",
            ],
        )

        payload = await ctx.import_file(template, ProductType.CRYPTO, content)

        assert sorted(_error_types(payload)) == ["MISSING_FIELD", "VALIDATION_ERROR"]
        assert await ctx.txs() == []

    @pytest.mark.asyncio
    async def test_fund_portfolio_fee_import(self, ctx):
        template = await ctx.template(ProductType.FUND_PORTFOLIO, PORTFOLIO_HEADERS)
        content = _csv(
            PORTFOLIO_HEADERS,
            [
                "p1",
                "Custody fee",
                "-12.5",
                "EUR",
                "FEE",
                "2025-03-31T00:00:00",
                "Robo",
                "ES9121000418450200051332",
            ],
            [
                "p2",
                "Contribution",
                "100",
                "EUR",
                "BUY",
                "2025-03-31T00:00:00",
                "Robo",
                "",
            ],
        )

        payload = await ctx.import_file(
            template, ProductType.FUND_PORTFOLIO, content, entity="Robo Advisor"
        )

        assert _error_types(payload) == ["VALIDATION_ERROR"]
        stored = await ctx.txs()
        assert len(stored) == 1
        assert stored[0]["product_type"] == "FUND_PORTFOLIO"
        assert stored[0]["type"] == "FEE"
        assert stored[0]["amount"] == 12.5
        assert stored[0]["portfolio_name"] == "Robo"
        assert stored[0]["iban"] == "ES9121000418450200051332"

    @pytest.mark.asyncio
    async def test_same_ref_across_products_is_allowed(self, ctx):
        account_template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        portfolio_template = await ctx.template(
            ProductType.FUND_PORTFOLIO, PORTFOLIO_HEADERS
        )
        await ctx.import_file(
            account_template,
            ProductType.ACCOUNT,
            _csv(
                ACCOUNT_HEADERS,
                ["r1", "Fee", "-1", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ),
        )

        payload = await ctx.import_file(
            portfolio_template,
            ProductType.FUND_PORTFOLIO,
            _csv(
                PORTFOLIO_HEADERS,
                ["r1", "Fee", "1", "EUR", "FEE", "2025-03-01T09:00:00", "Main", ""],
            ),
        )

        assert "errors" not in payload
        assert sorted(tx["product_type"] for tx in await ctx.txs()) == [
            "ACCOUNT",
            "FUND_PORTFOLIO",
        ]


class TestSheetsTransactionsImport:
    @pytest.mark.asyncio
    async def test_uses_entity_param_and_reimports_without_duplicates(self, ctx):
        bank = await ctx.entity("Sheets Bank")
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        ctx.configure_sheets(template, "Sheets Bank")
        ctx.sheets_port.read = AsyncMock(
            return_value=[
                ACCOUNT_HEADERS,
                ["s1", "Salary", "2500", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
                ["s2", "Rent", "-900", "EUR", "", "2025-03-02T09:00:00", "", "", ""],
            ]
        )

        first = await ctx.http.post(SHEETS_URL)
        second = await ctx.http.post(SHEETS_URL)

        for response in (first, second):
            assert response.status_code == 200
            assert "errors" not in await response.get_json()
        stored = _by_ref(await ctx.txs())
        assert set(stored) == {"s1", "s2"}
        assert {tx["entity"]["id"] for tx in stored.values()} == {str(bank.id)}
        assert {tx["source"] for tx in stored.values()} == {"SHEETS"}
        assert stored["s2"]["type"] == "OUTFLOW"

    @pytest.mark.asyncio
    async def test_skips_rows_already_imported_from_file(self, ctx):
        await ctx.entity("Sheets Bank")
        template = await ctx.template(ProductType.ACCOUNT, ACCOUNT_HEADERS)
        await ctx.import_file(
            template,
            ProductType.ACCOUNT,
            _csv(
                ACCOUNT_HEADERS,
                ["s1", "Salary", "2500", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
            ),
            entity="Sheets Bank",
        )
        ctx.configure_sheets(template, "Sheets Bank")
        ctx.sheets_port.read = AsyncMock(
            return_value=[
                ACCOUNT_HEADERS,
                ["s1", "Salary", "2500", "EUR", "", "2025-03-01T09:00:00", "", "", ""],
                ["s2", "Rent", "-900", "EUR", "", "2025-03-02T09:00:00", "", "", ""],
            ]
        )

        response = await ctx.http.post(SHEETS_URL)

        payload = await response.get_json()
        assert _error_types(payload) == ["DUPLICATED"]
        assert payload["errors"][0]["entry"] == "Movements"
        stored = await ctx.txs()
        assert sorted((tx["ref"], tx["source"]) for tx in stored) == [
            ("s1", "MANUAL"),
            ("s2", "SHEETS"),
        ]


class TestTransactionRefKeys:
    @pytest.mark.asyncio
    async def test_returns_keys_for_requested_entities_only(self, ctx):
        bank = await ctx.entity("Keys Bank")
        other = await ctx.entity("Other Bank")
        date = datetime(2025, 1, 1, tzinfo=tzlocal())
        common = dict(
            amount=Dezimal(10),
            currency="EUR",
            date=date,
            source=DataSource.MANUAL,
        )
        await ctx.tx_repo.save(
            Transactions(
                account=[
                    AccountTx(
                        id=uuid4(),
                        ref="acc",
                        name="Movement",
                        type=TxType.INFLOW,
                        entity=bank,
                        product_type=ProductType.ACCOUNT,
                        fees=Dezimal(0),
                        retentions=Dezimal(0),
                        **common,
                    ),
                    AccountTx(
                        id=uuid4(),
                        ref="other",
                        name="Movement",
                        type=TxType.INFLOW,
                        entity=other,
                        product_type=ProductType.ACCOUNT,
                        fees=Dezimal(0),
                        retentions=Dezimal(0),
                        **common,
                    ),
                ],
                investment=[
                    CryptoCurrencyTx(
                        id=uuid4(),
                        ref="crypto",
                        name="Bitcoin",
                        type=TxType.BUY,
                        entity=bank,
                        product_type=ProductType.CRYPTO,
                        currency_amount=Dezimal(1),
                        symbol="BTC",
                        price=Dezimal(10),
                        fees=Dezimal(0),
                        **common,
                    ),
                    FundPortfolioTx(
                        id=uuid4(),
                        ref="fee",
                        name="Fee",
                        type=TxType.FEE,
                        entity=bank,
                        product_type=ProductType.FUND_PORTFOLIO,
                        portfolio_name="Main",
                        **common,
                    ),
                ],
            )
        )

        keys = await ctx.tx_repo.get_ref_keys([bank.id])

        assert keys == {
            (bank.id, ProductType.ACCOUNT, "acc"),
            (bank.id, ProductType.CRYPTO, "crypto"),
            (bank.id, ProductType.FUND_PORTFOLIO, "fee"),
        }
        assert all(isinstance(key[0], UUID) for key in keys)
        both = await ctx.tx_repo.get_ref_keys([bank.id, other.id])
        assert (other.id, ProductType.ACCOUNT, "other") in both
        assert len(both) == 4

    @pytest.mark.asyncio
    async def test_empty_entity_list_returns_empty_set(self, ctx):
        assert await ctx.tx_repo.get_ref_keys([]) == set()


def _statement_pdf(stream_text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(stream_text.encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class TestTemplatelessHtmlAndPdfFileImport:
    @pytest.mark.asyncio
    async def test_imports_html_directly_with_ephemeral_template_fields_and_dedupes(
        self, ctx
    ):
        html = (
            "<html><body><table>"
            "<tr><th>Fecha</th><th>Concepto</th><th>Abono</th><th>Cargo</th></tr>"
            "<tr><td>15/01/2025</td><td>Nómina enero</td><td>1.500,00</td><td></td></tr>"
            "<tr><td>16/01/2025</td><td>Supermercado</td><td></td><td>45,30</td></tr>"
            "</table></body></html>"
        ).encode("utf-8")
        form = {
            "feature": "TRANSACTIONS",
            "product": "ACCOUNT",
            "numberFormat": "EUROPEAN",
            "templateFields": json.dumps(
                [
                    {"field": "date", "name": "Fecha"},
                    {"field": "name", "name": "Concepto"},
                    {"field": "amount_in", "name": "Abono"},
                    {"field": "amount_out", "name": "Cargo"},
                    {"field": "currency", "name": "currency", "default": "EUR"},
                ]
            ),
            "templateParams": json.dumps({"entity": "Direct HTML Bank"}),
        }

        preview_resp = await ctx.http.post(
            f"{IMPORT_URL}?preview=true",
            form=form,
            files={
                "file": FileStorage(
                    stream=io.BytesIO(html),
                    filename="statement.html",
                    content_type="text/html",
                )
            },
        )
        preview_body = await preview_resp.get_json()
        assert preview_body["code"] == "COMPLETED"
        assert len(preview_body["data"]["transactions"]["account"]) == 2
        assert await ctx.txs() == []

        commit_resp = await ctx.http.post(
            f"{IMPORT_URL}?preview=false",
            form=form,
            files={
                "file": FileStorage(
                    stream=io.BytesIO(html),
                    filename="statement.html",
                    content_type="text/html",
                )
            },
        )
        assert (await commit_resp.get_json())["code"] == "COMPLETED"
        stored = {tx["name"]: tx for tx in await ctx.txs()}
        assert stored["Nómina enero"]["type"] == "INFLOW"
        assert stored["Nómina enero"]["amount"] == 1500.0
        assert stored["Supermercado"]["type"] == "OUTFLOW"
        assert stored["Supermercado"]["amount"] == 45.3

        dup_resp = await ctx.http.post(
            f"{IMPORT_URL}?preview=false",
            form=form,
            files={
                "file": FileStorage(
                    stream=io.BytesIO(html),
                    filename="statement.html",
                    content_type="text/html",
                )
            },
        )
        assert _error_types(await dup_resp.get_json()) == ["DUPLICATED", "DUPLICATED"]
        assert len(await ctx.txs()) == 2

    @pytest.mark.asyncio
    async def test_imports_pdf_without_template_id_or_fields_and_reports_no_text_pdf(
        self, ctx
    ):
        pdf = _statement_pdf(
            "\n".join(
                [
                    "BT /F1 10 Tf 1 0 0 1 40 740 Tm (CUENTA EUR: ES91 2100 0418 4502 0005 1332) Tj ET",
                    "BT /F1 10 Tf 1 0 0 1 40 715 Tm (FECHA) Tj ET",
                    "BT /F1 10 Tf 1 0 0 1 130 715 Tm (DESCRIPCION) Tj ET",
                    "BT /F1 10 Tf 1 0 0 1 320 715 Tm (ENTRADA DE DINERO) Tj ET",
                    "BT /F1 10 Tf 1 0 0 1 450 715 Tm (SALIDA DE DINERO) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 40 694 Tm (15 ene) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 130 690 Tm (Nomina PDF) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 320 690 Tm (2.100,00 EUR) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 40 686 Tm (2025) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 40 664 Tm (18 ene) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 130 660 Tm (Compra PDF) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 450 660 Tm (32,15 EUR) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 40 656 Tm (2025) Tj ET",
                ]
            )
        )

        resp = await ctx.http.post(
            f"{IMPORT_URL}?preview=false",
            form={
                "feature": "TRANSACTIONS",
                "product": "ACCOUNT",
                "numberFormat": "EUROPEAN",
                "templateParams": json.dumps({"entity": "Direct PDF Bank"}),
            },
            files={
                "file": FileStorage(
                    stream=io.BytesIO(pdf),
                    filename="statement.pdf",
                    content_type="application/pdf",
                )
            },
        )
        body = await resp.get_json()
        assert body["code"] == "COMPLETED"
        stored = {tx["name"]: tx for tx in await ctx.txs()}
        assert stored["Nomina PDF"]["type"] == "INFLOW"
        assert stored["Nomina PDF"]["amount"] == 2100.0
        assert stored["Compra PDF"]["type"] == "OUTFLOW"
        assert stored["Compra PDF"]["amount"] == 32.15

        outlined_pdf = _statement_pdf("q 10 10 100 20 re S Q")
        bad_resp = await ctx.http.post(
            f"{IMPORT_URL}?preview=true",
            form={
                "feature": "TRANSACTIONS",
                "product": "ACCOUNT",
                "numberFormat": "EUROPEAN",
                "templateParams": json.dumps({"entity": "Direct PDF Bank"}),
            },
            files={
                "file": FileStorage(
                    stream=io.BytesIO(outlined_pdf),
                    filename="scanned.pdf",
                    content_type="application/pdf",
                )
            },
        )
        assert (await bad_resp.get_json())["code"] == "PDF_NO_TEXT_LAYER"


class TestRealStatementPdfImport:
    @staticmethod
    async def _import(ctx, name, form):
        resp = await ctx.http.post(
            f"{IMPORT_URL}?preview=false",
            form={
                "feature": "TRANSACTIONS",
                "product": "ACCOUNT",
                "templateParams": json.dumps({"entity": f"Real {name}"}),
                **form,
            },
            files={
                "file": FileStorage(
                    stream=io.BytesIO((RESOURCES / "statements" / name).read_bytes()),
                    filename=name,
                    content_type="application/pdf",
                )
            },
        )
        assert resp.status_code == 200
        return await resp.get_json()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name, number_format, count",
        [("b100.pdf", "EUROPEAN", 31), ("ing.pdf", "ENGLISH", 34)],
    )
    async def test_imports_every_movement_of_landscape_and_rotated_statements(
        self, ctx, name, number_format, count
    ):
        body = await self._import(ctx, name, {"numberFormat": number_format})

        assert body["code"] == "COMPLETED"
        assert _error_types(body) == ["UNEXPECTED_COLUMN"]
        assert len(await ctx.txs()) == count

    @pytest.mark.asyncio
    async def test_imports_statement_whose_header_is_only_on_the_first_page(self, ctx):
        body = await self._import(
            ctx,
            "myinvestor.pdf",
            {
                "numberFormat": "EUROPEAN",
                "templateFields": json.dumps(
                    [
                        {"field": "date", "name": "Fecha operación"},
                        {"field": "name", "name": "Concepto"},
                        {"field": "amount", "name": "Importe"},
                        {"field": "currency", "name": "currency", "default": "EUR"},
                    ]
                ),
            },
        )

        assert body["code"] == "COMPLETED"
        assert _error_types(body) == [
            "UNEXPECTED_COLUMN",
            "MISSING_FIELD",
            "MISSING_FIELD",
        ]
        response = await ctx.http.get("/api/v1/transactions?limit=200")
        txs = (await response.get_json())["transactions"]
        assert len(txs) == 115
        by_name = {tx["name"]: tx for tx in txs}
        assert by_name["SEGOFINANCE"]["type"] == "INFLOW"
        assert by_name["SEGOFINANCE"]["amount"] == 1.34
        assert by_name["Transferencia desde MyInvestor"]["type"] == "OUTFLOW"
        assert by_name["Transferencia desde MyInvestor"]["amount"] == 4990.0
