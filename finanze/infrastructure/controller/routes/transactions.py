from uuid import UUID

from domain.transactions import TransactionQueryRequest
from quart import jsonify, request


async def transactions(get_transactions_uc):
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    entities = request.args.getlist("entity")
    product_types = request.args.getlist("product_type")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    if to_date and len(to_date) == 10:
        to_date = f"{to_date}T23:59:59.999999"
    tx_types = request.args.getlist("type")
    historic_entry_id = request.args.get("historic_entry_id")
    if historic_entry_id:
        try:
            historic_entry_id = UUID(historic_entry_id)
        except ValueError:
            return jsonify({"error": "Invalid historic_entry_id format"}), 400

    try:
        labels = [UUID(label_id) for label_id in request.args.getlist("label")]
        excluded_labels = [
            UUID(label_id) for label_id in request.args.getlist("exclude_label")
        ]
    except ValueError:
        return jsonify({"error": "Invalid label format"}), 400
    unlabeled = request.args.get("unlabeled", "").lower() == "true"
    search = (request.args.get("search") or "").strip()[:100] or None

    query = TransactionQueryRequest(
        page=page,
        limit=limit,
        entities=list(entities) or None,
        product_types=list(product_types) or None,
        from_date=from_date,
        to_date=to_date,
        types=list(tx_types) or None,
        historic_entry_id=historic_entry_id,
        labels=labels or None,
        excluded_labels=excluded_labels or None,
        unlabeled=unlabeled,
        search=search,
    )

    result = await get_transactions_uc.execute(query)

    return jsonify({"transactions": result.transactions}), 200
