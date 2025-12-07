from io import BytesIO

import pandas as pd
from application.ports.file_rw_port import TableRWPort
from domain.exception.exceptions import UnsupportedFileFormat
from domain.export import FileFormat
from domain.file_upload import FileUpload


class XLSXFileTableAdapter(TableRWPort):
    def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        if format != FileFormat.XLSX:
            raise ValueError("XLSXFileTableAdapter only supports XLSX format")

        if not rows:
            raise ValueError("No rows provided for export")

        df = pd.DataFrame(rows)
        output = BytesIO()
        pd.DataFrame(df).to_excel(output, header=False, index=False)
        return output.getvalue()

    def parse(self, upload: FileUpload) -> list[list[str]]:
        if upload.content_type not in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ) and not upload.filename.endswith(".xlsx"):
            raise UnsupportedFileFormat("Unsupported XLSX file format")

        upload.data.seek(0)
        df = pd.read_excel(upload.data, header=None)
        return df.fillna("").astype(str).values.tolist()
