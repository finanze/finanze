from domain.use_cases.list_hugging_face_quants import ListHuggingFaceQuants
from quart import jsonify, request


async def list_hugging_face_quants(list_hugging_face_quants_uc: ListHuggingFaceQuants):
    repo = (request.args.get("repo") or "").strip()
    if not repo:
        return jsonify({"message": "Error: missing repository"}), 400

    result = await list_hugging_face_quants_uc.execute(repo)
    return jsonify(result), 200
