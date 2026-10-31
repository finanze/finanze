from uuid import UUID

from domain.labeling import UpdateTransactionLabelsRequest
from domain.use_cases.update_transaction_labels import UpdateTransactionLabels
from quart import jsonify, request


async def update_transaction_labels(
    update_transaction_labels_uc: UpdateTransactionLabels, tx_id: str
):
    body = await request.get_json()
    try:
        labels = body.get("labels") or []
        if not isinstance(labels, list):
            raise ValueError("labels must be a list of label IDs")
        update_request = UpdateTransactionLabelsRequest(
            tx_id=UUID(tx_id),
            label_ids=[UUID(str(label_id)) for label_id in labels],
            locked=bool(body.get("locked", True)),
            unlink=bool(body.get("unlink", False)),
            unpair=bool(body.get("unpair", False)),
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await update_transaction_labels_uc.execute(update_request)
    return "", 204
