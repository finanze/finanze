from io import BytesIO

import pytest

from domain.exception.exceptions import NoTableFound
from domain.export import FileFormat
from domain.file_upload import FileUpload
from infrastructure.table.html_file_table_adapter import HTMLFileTableAdapter


def _upload(html: str, charset: str = "utf-8") -> FileUpload:
    raw = html.encode(charset)
    return FileUpload(
        filename="movements.html",
        content_type="text/html",
        content_length=len(raw),
        data=BytesIO(raw),
    )


class TestHTMLFileTableAdapter:
    @pytest.mark.asyncio
    async def test_expands_rowspan_and_colspan_in_multi_row_headers(self):
        html = """<!doctype html>
        <html><body>
          <table>
            <tr>
              <th rowspan="2">Fecha</th>
              <th rowspan="2">Concepto</th>
              <th colspan="2">Importe</th>
            </tr>
            <tr>
              <th>Abono</th>
              <th>Cargo</th>
            </tr>
            <tr>
              <td>15/01/2025</td>
              <td>Nómina</td>
              <td>1.500,00 €</td>
              <td></td>
            </tr>
            <tr>
              <td>16/01/2025</td>
              <td>Supermercado</td>
              <td></td>
              <td>45,30 €</td>
            </tr>
          </table>
        </body></html>"""

        rows = await HTMLFileTableAdapter().parse(_upload(html))

        assert rows[1] == ["Fecha", "Concepto", "Abono", "Cargo"]
        assert rows[2] == ["15/01/2025", "Nómina", "1.500,00 €", ""]
        assert rows[3] == ["16/01/2025", "Supermercado", "", "45,30 €"]

    @pytest.mark.asyncio
    async def test_selects_movements_table_keeps_metadata_and_merges_pages(self):
        html = """<html><body>
          <table><tr><td><table>
            <tr><td>Cuenta</td><td>ES91 2100 0418 4502 0005 1332</td></tr>
            <tr><td>Divisa:</td><td>EUR</td></tr>
          </table></td></tr></table>
          <table>
            <tr><th>Fecha</th><th>Concepto</th><th>Importe</th></tr>
            <tr><td>02/01/2025</td><td>Nómina</td><td>1.500,00</td></tr>
          </table>
          <table>
            <tr><th>Fecha</th><th>Concepto</th><th>Importe</th></tr>
            <tr><td>05/01/2025</td><td>Café</td><td>-2,50</td></tr>
          </table>
          <table>
            <tr><td>Aviso legal del banco</td></tr>
          </table>
        </body></html>"""

        rows = await HTMLFileTableAdapter().parse(_upload(html))

        assert ["Divisa:", "EUR"] in rows[:3]
        header_idx = rows.index(["Fecha", "Concepto", "Importe"])
        assert rows[header_idx + 1 :] == [
            ["02/01/2025", "Nómina", "1.500,00"],
            ["05/01/2025", "Café", "-2,50"],
        ]

    @pytest.mark.asyncio
    async def test_rejects_html_without_tables(self):
        with pytest.raises(NoTableFound):
            await HTMLFileTableAdapter().parse(
                _upload("<html><body><p>Sin movimientos</p></body></html>")
            )

    @pytest.mark.asyncio
    async def test_convert_is_not_supported(self):
        with pytest.raises(ValueError):
            await HTMLFileTableAdapter().convert([["a"]], FileFormat.HTML)
