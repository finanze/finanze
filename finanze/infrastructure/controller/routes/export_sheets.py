from domain.exception.exceptions import ExportException
from domain.export import ExportRequest
from domain.use_cases.export_sheets import ExportSheets
from flask import jsonify, request
from pydantic import ValidationError


async def export_sheets(export_sheets_uc: ExportSheets):
    body = request.json
    try:
        export_request = ExportRequest(**body)
    except ValidationError:
        return "", 400

    try:
        await export_sheets_uc.execute(export_request)
    except ExportException as e:
        return jsonify({"message": str(e), "code": e.details}), 500

    return "", 204
