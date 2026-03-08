from uuid import UUID

from domain.global_position import ProductType
from domain.historic import HistoricQueryRequest, HistoricSortBy, SortOrder
from domain.use_cases.get_historic import GetHistoric
from quart import jsonify, request


async def get_historic(get_historic_uc: GetHistoric):
    raw_entities = request.args.getlist("entity")
    raw_product_types = request.args.getlist("product_type")

    entities = []
    product_types = []

    for e in raw_entities:
        try:
            entities.append(UUID(e))
        except ValueError:
            return jsonify(
                {"code": "INVALID_REQUEST", "message": f"Invalid entity UUID: {e}"}
            ), 400

    for pt in raw_product_types:
        try:
            product_types.append(ProductType(pt))
        except ValueError:
            return jsonify(
                {"code": "INVALID_REQUEST", "message": f"Invalid product_type: {pt}"}
            ), 400

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))

    raw_sort_by = request.args.get("sort_by")
    sort_by = HistoricSortBy.MATURITY
    if raw_sort_by:
        try:
            sort_by = HistoricSortBy(raw_sort_by)
        except ValueError:
            return jsonify(
                {
                    "code": "INVALID_REQUEST",
                    "message": f"Invalid sort_by: {raw_sort_by}",
                }
            ), 400

    raw_sort_order = request.args.get("sort_order")
    sort_order = SortOrder.DESC
    if raw_sort_order:
        try:
            sort_order = SortOrder(raw_sort_order)
        except ValueError:
            return jsonify(
                {
                    "code": "INVALID_REQUEST",
                    "message": f"Invalid sort_order: {raw_sort_order}",
                }
            ), 400

    query = HistoricQueryRequest(
        entities=entities or None,
        product_types=product_types or None,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    result = await get_historic_uc.execute(query)
    return jsonify({"entries": result.entries}), 200
