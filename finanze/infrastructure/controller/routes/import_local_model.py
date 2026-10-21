from domain.local_model import ImportLocalModelRequest
from domain.use_cases.import_local_model import ImportLocalModel
from quart import jsonify, request


async def import_local_model(import_local_model_uc: ImportLocalModel):
    body = await request.get_json(silent=True) or {}
    path = body.get("path")
    if not isinstance(path, str) or not path.strip():
        return jsonify({"message": "Error: missing path"}), 400

    result = await import_local_model_uc.execute(ImportLocalModelRequest(path=path))
    return jsonify(result), 200
