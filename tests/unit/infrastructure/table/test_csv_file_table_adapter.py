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
