from domain.exception.exceptions import ExportException
from domain.use_cases.export_sheets import ExportSheets
from quart import jsonify


async def export_sheets(export_sheets_uc: ExportSheets):
    try:
        await export_sheets_uc.execute()
    except ExportException as e:
        return jsonify({"message": str(e), "code": e.details}), 500

    return "", 204
