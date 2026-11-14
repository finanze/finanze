import codecs
from io import BytesIO

import pytest

from domain.export import FileFormat
from domain.file_upload import FileUpload
from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter


@pytest.mark.asyncio
async def test_convert_csv_prepends_utf8_bom():
    adapter = CSVFileTableAdapter()
    rows = [["name", "amount"], ["camión", "10"]]

    data = await adapter.convert(rows, FileFormat.CSV)

    assert data.startswith(codecs.BOM_UTF8)
    assert data.decode("utf-8-sig").splitlines()[1] == "camión,10"


@pytest.mark.asyncio
async def test_convert_tsv_prepends_utf8_bom():
    adapter = CSVFileTableAdapter()
    rows = [["name", "amount"], ["camión", "10"]]

    data = await adapter.convert(rows, FileFormat.TSV)

    assert data.startswith(codecs.BOM_UTF8)
    assert data.decode("utf-8-sig").splitlines()[1] == "camión\t10"


@pytest.mark.asyncio
async def test_parse_strips_utf8_bom():
    adapter = CSVFileTableAdapter()
    content = codecs.BOM_UTF8 + "name,amount\ncamión,10\n".encode("utf-8")
    upload = FileUpload(
        filename="data.csv",
        content_type="text/csv",
        content_length=len(content),
        data=BytesIO(content),
    )

    rows = await adapter.parse(upload)

    assert rows[0] == ["name", "amount"]
    assert rows[1] == ["camión", "10"]


def _upload(content: bytes, filename="data.csv", content_type="text/csv"):
    return FileUpload(
        filename=filename,
        content_type=content_type,
        content_length=len(content),
        data=BytesIO(content),
    )


@pytest.mark.asyncio
async def test_parse_detects_semicolon_delimiter_after_preamble():
    content = (
        "Cuenta;ES9121000418450200051332\n"
        "\n"
        "Fecha;Concepto;Importe;Saldo\n"
        "02/01/2025;Nómina, enero;1.500,00;2.500,00\n"
        "05/01/2025;Supermercado;-45,30;2.454,70\n"
    ).encode("utf-8")

    rows = await CSVFileTableAdapter().parse(_upload(content))

    assert rows[2] == ["Fecha", "Concepto", "Importe", "Saldo"]
    assert rows[3] == ["02/01/2025", "Nómina, enero", "1.500,00", "2.500,00"]


@pytest.mark.asyncio
async def test_parse_falls_back_to_cp1252():
    content = "Fecha;Concepto\n02/01/2025;Nómina €\n".encode("cp1252")

    rows = await CSVFileTableAdapter().parse(_upload(content))

    assert rows[1] == ["02/01/2025", "Nómina €"]


@pytest.mark.asyncio
async def test_parse_decodes_utf16_with_bom():
    content = "Fecha\tConcepto\n02/01/2025\tNómina\n".encode("utf-16")

    rows = await CSVFileTableAdapter().parse(_upload(content))

    assert rows[1] == ["02/01/2025", "Nómina"]


@pytest.mark.asyncio
async def test_parse_tsv_always_uses_tabs():
    content = "name,label\tamount\nSalary,monthly\t10\n".encode("utf-8")

    rows = await CSVFileTableAdapter().parse(_upload(content, filename="data.tsv"))

    assert rows == [["name,label", "amount"], ["Salary,monthly", "10"]]
