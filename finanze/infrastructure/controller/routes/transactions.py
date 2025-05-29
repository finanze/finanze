from flask import request, jsonify

from domain.transactions import TransactionQueryRequest


def transactions(get_transactions_uc):
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    entities = request.args.getlist('entity')
    excluded_entities = request.args.getlist('excluded_entity')
    product_types = request.args.getlist('product_type')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    tx_types = request.args.getlist('type')

    query = TransactionQueryRequest(
        page=page,
        limit=limit,
        entities=[e for e in entities] or None,
        excluded_entities=[ee for ee in excluded_entities] or None,
        product_types=[pt for pt in product_types] or None,
        from_date=from_date,
        to_date=to_date,
        types=[tx_type for tx_type in tx_types] or None
    )

    result = get_transactions_uc.execute(query)

    return jsonify({"transactions": result.transactions}), 200
