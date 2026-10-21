from domain.local_model import DownloadLocalModelRequest
from domain.use_cases.download_local_model import DownloadLocalModel
from quart import jsonify, request


async def download_local_model(download_local_model_uc: DownloadLocalModel):
    body = await request.get_json(silent=True) or {}
    catalog_id = body.get("catalog_id")
    repo = body.get("repo")
    quant = body.get("quant")
    if not all(isinstance(v, str) or v is None for v in (catalog_id, repo, quant)):
        return jsonify({"message": "Error: invalid model"}), 400
    if not catalog_id and not (repo and quant):
        return jsonify({"message": "Error: missing model"}), 400

    await download_local_model_uc.execute(
        DownloadLocalModelRequest(catalog_id=catalog_id, repo=repo, quant=quant)
    )
    return "", 204
