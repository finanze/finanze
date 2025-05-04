from flask import request
from pydantic import ValidationError

from domain.export import ExportRequest
from domain.use_cases.update_sheets import UpdateSheets


def export(update_sheets: UpdateSheets):
    body = request.json
    try:
        export_request = ExportRequest(**body)
    except ValidationError as e:
        return "", 400

    update_sheets.execute(export_request)
    return "", 204
