from domain.exception.exceptions import ExportException
from domain.export import ExportRequest
from domain.use_cases.update_sheets import UpdateSheets
from flask import jsonify, request
from pydantic import ValidationError


async def export(update_sheets: UpdateSheets):
    body = request.json
    try:
        export_request = ExportRequest(**body)
    except ValidationError:
        return "", 400

    try:
        await update_sheets.execute(export_request)
    except ExportException as e:
        return jsonify({"message": str(e), "code": e.details}), 500

    return "", 204
