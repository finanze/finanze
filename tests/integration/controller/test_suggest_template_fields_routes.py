import io
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from werkzeug.datastructures import FileStorage

from application.ports.template_port import TemplatePort
from application.use_cases.suggest_template_fields import SuggestTemplateFieldsImpl
from domain.entity import Feature
from domain.export import FileFormat
from domain.global_position import ProductType
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.suggest_template_fields import (
    suggest_template_fields,
)
from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
from infrastructure.table.html_file_table_adapter import HTMLFileTableAdapter
from infrastructure.table.pdf_file_table_adapter import PDFFileTableAdapter
from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
from infrastructure.templating.templated_data_parser import TemplateDataParser

SUGGEST_URL = "/api/v1/templates/suggest"
RESOURCES = Path(__file__).resolve().parents[2] / "resources" / "import"


class InMemoryTemplatePort(TemplatePort):
    def __init__(self):
        self.templates: list[Template] = []

    async def save(self, template: Template):
        self.templates.append(template)

    async def update(self, template: Template):
        raise NotImplementedError

    async def delete(self, template_id):
        raise NotImplementedError

    async def get_by_id(self, template_id):
        raise NotImplementedError

    async def get_by_type(self, template_type: TemplateType) -> list[Template]:
        return [t for t in self.templates if t.type == template_type]

    async def get_by_name_and_type(self, name, template_type):
        raise NotImplementedError


def _template(fields, feature=Feature.TRANSACTIONS, products=None):
    return Template(
        id=uuid4(),
        name="Bank",
        feature=feature,
        type=TemplateType.IMPORT,
        fields=fields,
        products=products,
    )


@pytest_asyncio.fixture
async def template_port():
    return InMemoryTemplatePort()


@pytest_asyncio.fixture
async def client(tmp_path, template_port):
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
    use_case = SuggestTemplateFieldsImpl(table_rw, TemplateDataParser(), template_port)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route(SUGGEST_URL, methods=["POST"])
    async def suggest_handler():
        return await suggest_template_fields(use_case)

    return app.test_client()


async def _suggest(
    client,
    content,
    filename="movements.csv",
    content_type="text/csv",
    feature="TRANSACTIONS",
    product="ACCOUNT",
):
    return await client.post(
        SUGGEST_URL,
        form={"feature": feature, "product": product},
        files={
            "file": FileStorage(
                stream=io.BytesIO(content),
                filename=filename,
                content_type=content_type,
            )
        },
    )


def _simple_pdf(stream_text: str) -> bytes:
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


class TestSuggestTemplateFieldsRoute:
    @pytest.mark.asyncio
    async def test_suggests_mapping_for_legacy_xls(self, client):
        response = await _suggest(
            client,
            (RESOURCES / "bank_movements.xls").read_bytes(),
            filename="movements.xls",
            content_type="application/vnd.ms-excel",
        )

        assert response.status_code == 200
        assert await response.get_json() == {
            "headers": ["Fecha operación", "Concepto", "Importe", "Saldo", "Divisa"],
            "fields": [
                {"field": "date", "name": "Fecha operación"},
                {"field": "name", "name": "Concepto"},
                {"field": "amount", "name": "Importe"},
                {"field": "currency", "name": "Divisa"},
            ],
            "number_format": None,
            "date_format": None,
            "detected_currency": "EUR",
            "missing_required_fields": [],
            "matching_templates": [],
        }

    @pytest.mark.asyncio
    async def test_returns_detected_formats_and_matching_templates(
        self, client, template_port
    ):
        account_fields = [
            TemplatedField(field="date", name="Fecha"),
            TemplatedField(field="name", name="Concepto"),
            TemplatedField(field="amount", name="Importe"),
            TemplatedField(field="currency", name="currency", default_value="EUR"),
        ]
        partial = _template(account_fields)
        complete = _template(
            account_fields + [TemplatedField(field="ref", name="Referencia")],
            products=[ProductType.ACCOUNT],
        )
        other_product = _template(account_fields, products=[ProductType.CRYPTO])
        positions = _template(
            [TemplatedField(field="name", name="Concepto")], feature=Feature.POSITION
        )
        template_port.templates = [partial, other_product, positions, complete]
        content = (
            "Fecha;Concepto;Importe;Referencia\n"
            "25/01/2025;Nómina;1.500,00;A1\n"
            "26/01/2025;Café;-2,50;A2\n"
        ).encode("utf-8")

        response = await _suggest(client, content)

        assert response.status_code == 200
        body = await response.get_json()
        assert body["number_format"] == "EUROPEAN"
        assert body["date_format"] == "%d/%m/%Y"
        assert body["matching_templates"] == [str(complete.id), str(partial.id)]

    @pytest.mark.asyncio
    async def test_suggests_investment_mapping_from_csv(self, client):
        content = (
            "Fecha;ISIN;Títulos;Importe\n02/01/2025;US0378331005;2;300,00\n"
        ).encode("utf-8")

        response = await _suggest(client, content, product="STOCK_ETF")

        assert response.status_code == 200
        assert (await response.get_json())["fields"] == [
            {"field": "date", "name": "Fecha"},
            {"field": "isin", "name": "ISIN"},
            {"field": "shares", "name": "Títulos"},
            {"field": "amount", "name": "Importe"},
        ]

    @pytest.mark.parametrize(
        "feature,product",
        [
            ("UNKNOWN", "ACCOUNT"),
            ("TRANSACTIONS", "UNKNOWN"),
            ("HISTORIC", "STOCK_ETF"),
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_invalid_feature_or_product(self, client, feature, product):
        response = await _suggest(client, b"Fecha\n", feature=feature, product=product)

        assert response.status_code == 400
        assert (await response.get_json())["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_rejects_unsupported_files(self, client):
        response = await _suggest(
            client,
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1corrupted",
            filename="movements.xls",
            content_type="application/vnd.ms-excel",
        )

        assert response.status_code == 400
        assert (await response.get_json())["code"] == "UNSUPPORTED_FILE_FORMAT"

    @pytest.mark.asyncio
    async def test_requires_file(self, client):
        response = await client.post(
            SUGGEST_URL, form={"feature": "TRANSACTIONS", "product": "ACCOUNT"}
        )

        assert response.status_code == 400
        assert (await response.get_json())["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_suggests_fields_for_html_and_pdf_statements(self, client):
        html = (
            "<html><body><table>"
            "<tr><th>Fecha</th><th>Concepto</th><th>Importe (€)</th></tr>"
            "<tr><td>15/01/2025</td><td>Nómina</td><td>1.500,00</td></tr>"
            "</table></body></html>"
        ).encode("utf-8")
        html_resp = await _suggest(
            client, html, filename="statement.html", content_type="text/html"
        )
        assert html_resp.status_code == 200
        html_body = await html_resp.get_json()
        assert html_body["detected_currency"] == "EUR"
        assert html_body["missing_required_fields"] == ["currency"]
        assert html_body["fields"] == [
            {"field": "date", "name": "Fecha"},
            {"field": "name", "name": "Concepto"},
            {"field": "amount", "name": "Importe (€)"},
        ]

        pdf = _simple_pdf(
            "\n".join(
                [
                    "BT /F1 10 Tf 1 0 0 1 40 720 Tm (Fecha) Tj ET",
                    "BT /F1 10 Tf 1 0 0 1 140 720 Tm (Concepto) Tj ET",
                    "BT /F1 10 Tf 1 0 0 1 360 720 Tm (Importe) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 40 700 Tm (15/01/2025) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 140 700 Tm (Nomina) Tj ET",
                    "BT /F1 9 Tf 1 0 0 1 360 700 Tm (1.500,00 EUR) Tj ET",
                ]
            )
        )
        pdf_resp = await _suggest(
            client, pdf, filename="statement.pdf", content_type="application/pdf"
        )
        assert pdf_resp.status_code == 200
        pdf_body = await pdf_resp.get_json()
        assert pdf_body["detected_currency"] == "EUR"
        assert pdf_body["number_format"] == "EUROPEAN"
        assert pdf_body["date_format"] == "%d/%m/%Y"

    @pytest.mark.asyncio
    async def test_returns_specific_codes_for_outlined_pdf_and_tableless_html(
        self, client
    ):
        outlined_pdf = _simple_pdf("q 10 10 100 20 re S Q")
        pdf_resp = await _suggest(
            client,
            outlined_pdf,
            filename="scanned.pdf",
            content_type="application/pdf",
        )
        assert pdf_resp.status_code == 400
        assert (await pdf_resp.get_json())["code"] == "PDF_NO_TEXT_LAYER"

        tableless_html = await _suggest(
            client,
            b"<html><body><p>Sin tabla</p></body></html>",
            filename="page.html",
            content_type="text/html",
        )
        assert tableless_html.status_code == 400
        assert (await tableless_html.get_json())["code"] == "NO_TABLE_FOUND"
