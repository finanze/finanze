from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from domain.dezimal import Dezimal
from domain.exception.exceptions import UnsupportedFileFormat
from domain.file_upload import FileUpload
from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter

RESOURCES = Path(__file__).resolve().parents[3] / "resources" / "import"


def _upload(data: bytes, filename="movements.xls"):
    return FileUpload(
        filename=filename,
        content_type="application/vnd.ms-excel",
        content_length=len(data),
        data=BytesIO(data),
    )


async def _parse(data: bytes, filename="movements.xls"):
    return await XLSXFileTableAdapter().parse(_upload(data, filename))


class TestXLSXFileTableAdapterParse:
    @pytest.mark.asyncio
    async def test_parses_legacy_xls_with_typed_cells(self):
        rows = await _parse((RESOURCES / "bank_movements.xls").read_bytes())

        assert rows[0][0] == "Movimientos de la cuenta"
        assert rows[3] == ["Fecha operación", "Concepto", "Importe", "Saldo", "Divisa"]
        assert rows[4] == [
            datetime(2025, 1, 2),
            "Nómina enero",
            Dezimal(1500),
            Dezimal(2500),
            "EUR",
        ]
        assert rows[5][2] == Dezimal("-45.3")

    @pytest.mark.asyncio
    async def test_parses_xlsx_with_typed_cells(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Fecha", "Importe", "Unidades", "Activo", "Nota"])
        sheet.append([datetime(2025, 1, 2, 10, 30), 1.5, 3, True, None])
        output = BytesIO()
        workbook.save(output)

        rows = await _parse(output.getvalue(), "movements.xlsx")

        assert rows == [
            ["Fecha", "Importe", "Unidades", "Activo", "Nota"],
            [datetime(2025, 1, 2, 10, 30), Dezimal("1.5"), Dezimal(3), True, ""],
        ]

    @pytest.mark.asyncio
    async def test_parses_html_table_saved_as_xls(self):
        html = (
            "<html><head><meta http-equiv='Content-Type' "
            "content='text/html; charset=iso-8859-1'></head><body>"
            "<table><tr><td colspan='2'>Movimientos</td></tr>"
            "<tr><th>Fecha</th><th>Concepto</th><th>Importe</th></tr>"
            "<tr><td>02/01/2025</td><td>Nómina&nbsp;enero<br>Empresa</td>"
            "<td>1.500,00</td></tr></table></body></html>"
        ).encode("iso-8859-1")

        rows = await _parse(html)

        assert rows == [
            ["Movimientos", ""],
            ["Fecha", "Concepto", "Importe"],
            ["02/01/2025", "Nómina enero Empresa", "1.500,00"],
        ]

    @pytest.mark.asyncio
    async def test_parses_spreadsheetml_saved_as_xls(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Movimientos">
  <Table>
   <Row><Cell ss:MergeAcross="1"><Data ss:Type="String">Cuenta</Data></Cell></Row>
   <Row ss:Index="3">
    <Cell><Data ss:Type="String">Fecha</Data></Cell>
    <Cell><Data ss:Type="String">Concepto</Data></Cell>
    <Cell ss:Index="4"><Data ss:Type="String">Importe</Data></Cell>
   </Row>
   <Row>
    <Cell><Data ss:Type="DateTime">2025-01-02T00:00:00.000</Data></Cell>
    <Cell><Data ss:Type="String">Nómina</Data></Cell>
    <Cell ss:Index="4"><Data ss:Type="Number">-45.3</Data></Cell>
   </Row>
  </Table>
 </Worksheet>
</Workbook>""".encode("utf-8")

        rows = await _parse(xml)

        assert rows == [
            ["Cuenta", ""],
            [],
            ["Fecha", "Concepto", "", "Importe"],
            [datetime(2025, 1, 2), "Nómina", "", Dezimal("-45.3")],
        ]

    @pytest.mark.asyncio
    async def test_rejects_spreadsheetml_with_doctype(self):
        xml = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol">]>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet><Table><Row><Cell><Data>&lol;</Data></Cell></Row></Table></Worksheet>
</Workbook>"""

        with pytest.raises(UnsupportedFileFormat):
            await _parse(xml)

    @pytest.mark.parametrize(
        "data",
        [
            b"\x00\x01\x02 not a spreadsheet",
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1corrupted",
            b"PK\x03\x04corrupted",
            b"<html><body><p>No table here</p></body></html>",
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_unsupported_content(self, data):
        with pytest.raises(UnsupportedFileFormat):
            await _parse(data)
