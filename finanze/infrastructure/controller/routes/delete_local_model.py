from domain.local_model import LocalModelRequest
from domain.use_cases.delete_local_model import DeleteLocalModel
from quart import jsonify, request


async def delete_local_model(delete_local_model_uc: DeleteLocalModel):
    model_id = (request.args.get("model_id") or "").strip()
    if not model_id:
        return jsonify({"message": "Error: missing model"}), 400

    await delete_local_model_uc.execute(LocalModelRequest(model_id=model_id))
    return "", 204
