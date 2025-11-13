from flask import jsonify

from domain.use_cases.import_sheets import ImportSheets


async def import_sheets(import_sheets_uc: ImportSheets):
    result = await import_sheets_uc.execute()

    response = {"code": result.code.name}
    if result.data:
        response["data"] = result.data
    if result.errors:
        response["errors"] = result.errors

    return jsonify(response), 200
