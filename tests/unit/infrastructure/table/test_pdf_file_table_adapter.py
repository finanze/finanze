from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from domain.exception.exceptions import (
    NoTableFound,
    PdfNoTextLayer,
    UnsupportedFileFormat,
)
from domain.export import FileFormat
from domain.file_upload import FileUpload
from infrastructure.table.pdf_file_table_adapter import PDFFileTableAdapter


def _pdf_escape(text: str) -> str:
    encoded = text.encode("cp1252", errors="replace")
    parts = []
    for byte in encoded:
        if byte in (0x28, 0x29, 0x5C):
            parts.append(f"\\{chr(byte)}")
        elif 32 <= byte <= 126:
            parts.append(chr(byte))
        else:
            parts.append(f"\\{byte:03o}")
    return "".join(parts)


def _text_cmd(x: int, y: int, size: int, text: str, bold: bool = False) -> str:
    font = "/F2" if bold else "/F1"
    return f"BT {font} {size} Tf 1 0 0 1 {x} {y} Tm ({_pdf_escape(text)}) Tj ET"


def _build_pdf(page_streams: list[str]) -> bytes:
    writer = PdfWriter()
    for stream_content in page_streams:
        page = writer.add_blank_page(width=595, height=842)
        f1 = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        f2 = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        fonts = DictionaryObject(
            {
                NameObject("/F1"): writer._add_object(f1),
                NameObject("/F2"): writer._add_object(f2),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
        stream = DecodedStreamObject()
        stream.set_data(stream_content.encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _upload(data: bytes) -> FileUpload:
    return FileUpload(
        filename="statement.pdf",
        content_type="application/pdf",
        content_length=len(data),
        data=BytesIO(data),
    )


class TestPDFFileTableAdapter:
    @pytest.mark.asyncio
    async def test_reconstructs_out_of_order_columns_and_centered_multiline_cells(self):
        page_stream = "\n".join(
            [
                _text_cmd(180, 765, 11, "Extracto de movimientos de cuenta", bold=True),
                _text_cmd(180, 740, 10, "CUENTA EUR: ES91 2100 0418 4502 0005 1332"),
                _text_cmd(55, 714, 10, "Fecha", bold=True),
                _text_cmd(125, 714, 10, "F. valor", bold=True),
                _text_cmd(210, 714, 10, "Concepto", bold=True),
                _text_cmd(395, 714, 10, "Importe", bold=True),
                _text_cmd(490, 714, 10, "Saldo", bold=True),
                # Emit all dates first (out-of-order PDF stream)
                _text_cmd(55, 688, 9, "10/01/2025"),
                _text_cmd(55, 652, 9, "12/01/2025"),
                # Vertically centered 3-line Concepto on row 1 (above + at + below 688)
                _text_cmd(125, 697, 9, "TRASPASO"),
                _text_cmd(125, 688, 9, "NOMINA EMPRESA"),
                _text_cmd(125, 679, 9, "ENERO"),
                _text_cmd(130, 688, 9, "10-01"),
                _text_cmd(400, 688, 9, "1.500,00"),
                _text_cmd(490, 688, 9, "2.500,00"),
                # Wait: keep F. valor in its own X band (125..160) and Concepto at 185
            ]
        )
        # Re-emit with clean X positions matching bank statements
        page_stream = "\n".join(
            [
                _text_cmd(180, 765, 11, "Extracto de movimientos de cuenta", bold=True),
                _text_cmd(180, 740, 10, "CUENTA EUR: ES91 2100 0418 4502 0005 1332"),
                _text_cmd(55, 714, 10, "Fecha", bold=True),
                _text_cmd(125, 714, 10, "F. valor", bold=True),
                _text_cmd(220, 714, 10, "Concepto", bold=True),
                _text_cmd(400, 714, 10, "Importe", bold=True),
                _text_cmd(495, 714, 10, "Saldo", bold=True),
                _text_cmd(55, 688, 9, "10/01/2025"),
                _text_cmd(55, 652, 9, "12/01/2025"),
                _text_cmd(130, 688, 9, "10-01"),
                _text_cmd(180, 697, 9, "TRASPASO"),
                _text_cmd(180, 688, 9, "NOMINA EMPRESA"),
                _text_cmd(180, 679, 9, "ENERO"),
                _text_cmd(405, 688, 9, "1.500,00"),
                _text_cmd(495, 688, 9, "2.500,00"),
                _text_cmd(130, 652, 9, "12-01"),
                _text_cmd(180, 661, 9, "RECIBO LUZ"),
                _text_cmd(180, 652, 9, "REF 9988"),
                _text_cmd(410, 652, 9, "-45,30"),
                _text_cmd(495, 652, 9, "2.454,70"),
            ]
        )

        rows = await PDFFileTableAdapter().parse(_upload(_build_pdf([page_stream])))

        assert rows[0] == ["Extracto de movimientos de cuenta"]
        assert rows[1] == ["CUENTA EUR: ES91 2100 0418 4502 0005 1332"]
        assert rows[2] == ["Fecha", "F. valor", "Concepto", "Importe", "Saldo"]
        assert rows[3] == [
            "10/01/2025",
            "10-01",
            "TRASPASO NOMINA EMPRESA ENERO",
            "1.500,00",
            "2.500,00",
        ]
        assert rows[4] == [
            "12/01/2025",
            "12-01",
            "RECIBO LUZ REF 9988",
            "-45,30",
            "2.454,70",
        ]

    @pytest.mark.asyncio
    async def test_stitches_multipage_tables_dedupes_headers_and_skips_opening_balance(
        self,
    ):
        header_ops = [
            _text_cmd(30, 700, 9, "Fecha", bold=True),
            _text_cmd(100, 700, 9, "Concepto", bold=True),
            _text_cmd(350, 700, 9, "Importe", bold=True),
            _text_cmd(450, 700, 9, "Saldo", bold=True),
        ]
        page1 = "\n".join(
            [
                *header_ops,
                _text_cmd(100, 682, 9, "SALDO ANTERIOR"),
                _text_cmd(450, 682, 9, "1.000,00 EUR"),
                _text_cmd(30, 664, 9, "02/01/2025"),
                _text_cmd(100, 664, 9, "Nomina"),
                _text_cmd(350, 664, 9, "1.500,00 EUR"),
                _text_cmd(450, 664, 9, "2.500,00 EUR"),
                _text_cmd(280, 20, 8, "- 1 -"),
            ]
        )
        page2 = "\n".join(
            [
                *header_ops,
                *header_ops,  # Faux-bold double-drawn header
                _text_cmd(30, 664, 9, "05/01/2025"),
                _text_cmd(100, 664, 9, "Supermercado"),
                _text_cmd(350, 664, 9, "-45,30 EUR"),
                _text_cmd(450, 664, 9, "2.454,70 EUR"),
                _text_cmd(280, 20, 8, "- 2 -"),
            ]
        )

        rows = await PDFFileTableAdapter().parse(_upload(_build_pdf([page1, page2])))

        assert rows == [
            ["Fecha", "Concepto", "Importe", "Saldo"],
            ["02/01/2025", "Nomina", "1.500,00 EUR", "2.500,00 EUR"],
            ["05/01/2025", "Supermercado", "-45,30 EUR", "2.454,70 EUR"],
        ]

    @pytest.mark.asyncio
    async def test_selects_transactions_over_summary_with_stacked_headers_and_split_dates(
        self,
    ):
        page1 = "\n".join(
            [
                _text_cmd(48, 620, 11, "RESUMEN DE CUENTA", bold=True),
                _text_cmd(48, 590, 6, "PRODUCTO", bold=True),
                _text_cmd(220, 590, 6, "ENTRADA DE DINERO", bold=True),
                _text_cmd(360, 590, 6, "SALIDA DE DINERO", bold=True),
                _text_cmd(48, 574, 7, "Cuenta efectivo"),
                _text_cmd(220, 574, 7, "1.500,00 €"),
                _text_cmd(360, 574, 7, "45,30 €"),
                _text_cmd(48, 520, 11, "TRANSACCIONES DE CUENTA", bold=True),
                _text_cmd(48, 490, 6, "FECHA", bold=True),
                _text_cmd(95, 490, 6, "TIPO", bold=True),
                _text_cmd(170, 490, 6, "DESCRIPCION", bold=True),
                _text_cmd(370, 490, 6, "ENTRADA DE", bold=True),
                _text_cmd(445, 490, 6, "SALIDA DE", bold=True),
                _text_cmd(520, 490, 6, "BALANCE", bold=True),
                _text_cmd(370, 484, 6, "DINERO", bold=True),
                _text_cmd(445, 484, 6, "DINERO", bold=True),
                _text_cmd(48, 464, 7, "15 ene"),
                _text_cmd(95, 460, 7, "Transferencia"),
                _text_cmd(170, 460, 7, "Nomina enero"),
                _text_cmd(370, 460, 7, "1.500,00 €"),
                _text_cmd(520, 460, 7, "2.500,00 €"),
                _text_cmd(48, 456, 7, "2025"),
                _text_cmd(48, 432, 7, "18 ene"),
                _text_cmd(95, 428, 7, "Tarjeta"),
                _text_cmd(170, 428, 7, "Supermercado"),
                _text_cmd(445, 428, 7, "45,30 €"),
                _text_cmd(520, 428, 7, "2.454,70 €"),
                _text_cmd(48, 424, 7, "2025"),
                _text_cmd(48, 360, 11, "NOTAS LEGALES", bold=True),
                _text_cmd(48, 342, 6, "Texto informativo sin movimientos"),
            ]
        )

        rows = await PDFFileTableAdapter().parse(_upload(_build_pdf([page1])))

        header_idx = rows.index(
            [
                "FECHA",
                "TIPO",
                "DESCRIPCION",
                "ENTRADA DE DINERO",
                "SALIDA DE DINERO",
                "BALANCE",
            ]
        )
        assert rows[header_idx + 1 :] == [
            [
                "15 ene 2025",
                "Transferencia",
                "Nomina enero",
                "1.500,00 €",
                "",
                "2.500,00 €",
            ],
            [
                "18 ene 2025",
                "Tarjeta",
                "Supermercado",
                "",
                "45,30 €",
                "2.454,70 €",
            ],
        ]

    @pytest.mark.asyncio
    async def test_raises_pdf_no_text_layer_for_vector_outlined_pdf(self):
        vector_only = "q 10 10 100 20 re S 20 20 m 80 20 l 80 40 20 40 20 20 c S Q"
        pdf_bytes = _build_pdf([vector_only])

        with pytest.raises(PdfNoTextLayer):
            await PDFFileTableAdapter().parse(_upload(pdf_bytes))

    @pytest.mark.asyncio
    async def test_raises_no_table_found_for_prose_pdf(self):
        prose = _text_cmd(50, 750, 11, "Certificado de titularidad bancaria sin tablas")
        with pytest.raises(NoTableFound):
            await PDFFileTableAdapter().parse(_upload(_build_pdf([prose])))

    @pytest.mark.asyncio
    async def test_rejects_corrupted_pdf_bytes(self):
        with pytest.raises(UnsupportedFileFormat):
            await PDFFileTableAdapter().parse(_upload(b"%PDF-1.4 broken"))

    @pytest.mark.asyncio
    async def test_convert_is_not_supported(self):
        with pytest.raises(ValueError):
            await PDFFileTableAdapter().convert([["a"]], FileFormat.PDF)
