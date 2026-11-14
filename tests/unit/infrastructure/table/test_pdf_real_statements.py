from io import BytesIO
from pathlib import Path

import pytest

from domain.exception.exceptions import PdfNoTextLayer
from domain.file_upload import FileUpload
from infrastructure.table.pdf_file_table_adapter import PDFFileTableAdapter

STATEMENTS = Path(__file__).resolve().parents[3] / "resources" / "import" / "statements"


async def _parse(name: str) -> list[list[str]]:
    data = (STATEMENTS / name).read_bytes()
    upload = FileUpload(
        filename=name,
        content_type="application/pdf",
        content_length=len(data),
        data=BytesIO(data),
    )
    return await PDFFileTableAdapter().parse(upload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, header, count, first, last",
    [
        (
            "myinvestor.pdf",
            [
                "Fecha operación",
                "Fecha valor",
                "Operacion",
                "Concepto",
                "Tipo",
                "Importe",
                "Saldo",
            ],
            117,
            [
                "09/09/2026",
                "11/09/2026",
                "SUSCRIPCION IIC",
                "ISHARES DEVELOPED WORLD INDEX",
                "",
                "-14,95",
                "32.987,13 €",
            ],
            [
                "09/07/2026",
                "10/07/2026",
                "SUSCRIPCION IIC",
                "VANGUARD EUROPEAN STOCK INDEX",
                "",
                "-18,42",
                "25.204,27 €",
            ],
        ),
        (
            "b100.pdf",
            [
                "F.VALOR",
                "F.CONTABLE",
                "F.OPERACIÓN",
                "TIPO OPERACIÓN",
                "DESCRIPCIÓN",
                "IMPORTE",
                "SALDO",
                "DIVISA",
            ],
            31,
            [
                "04/11/2026",
                "04/11/2026",
                "04/11/2026",
                "Gasto",
                "AHORRO PARA HUCHA PRINCIPAL 20:39:2 9",
                "-1.400,00",
                "0,00",
                "EUR",
            ],
            [
                "30/06/2026",
                "30/06/2026",
                "30/06/2026",
                "Ingreso",
                "JORGE ALAMO PRADO",
                "1.300,00",
                "1.300,00",
                "EUR",
            ],
        ),
        (
            "ing.pdf",
            [
                "F. VALOR",
                "CATEGORÍA",
                "SUBCATEGORÍA",
                "DESCRIPCIÓN",
                "COMENTARIO",
                "IMPORTE (€)",
                "SALDO (€)",
            ],
            34,
            [
                "04/10/2026",
                "Otros gastos",
                "Transferencias",
                "Transferencia emitida a JORGE ALAMO PRADO Movimiento ING",
                "",
                "-500.00",
                "0.00",
            ],
            [
                "20/11/2023",
                "Movimientos excluidos",
                "Traspaso entre cuentas",
                "Traspaso recibido Cuenta Nómina Movimiento ING",
                "",
                "3,000.00",
                "3,000.00",
            ],
        ),
    ],
    ids=[
        "landscape-header-only-on-first-page",
        "landscape-page-header-box",
        "rotated-page",
    ],
)
async def test_parses_every_movement_of_real_statements(
    name, header, count, first, last
):
    rows = await _parse(name)

    movements = rows[rows.index(header) + 1 :]
    assert len(movements) == count
    assert movements[0] == first
    assert movements[-1] == last


@pytest.mark.asyncio
async def test_scanned_statement_has_no_text_layer():
    with pytest.raises(PdfNoTextLayer):
        await _parse("myinvestor_scanned.pdf")
