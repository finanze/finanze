from uuid import UUID

from domain.global_position import ProductType
from domain.historic import HistoricQueryRequest
from domain.use_cases.get_historic import GetHistoric
from flask import jsonify, request


def get_historic(get_historic_uc: GetHistoric):
    raw_entities = request.args.getlist("entity")
    raw_product_types = request.args.getlist("product_type")

    entities = []
    product_types = []

    for e in raw_entities:
        try:
            entities.append(UUID(e))
        except ValueError:
            return jsonify({"error": f"Invalid entity UUID: {e}"}), 400

    for pt in raw_product_types:
        try:
            product_types.append(ProductType(pt))
        except ValueError:
            return jsonify({"error": f"Invalid product_type: {pt}"}), 400

    query = HistoricQueryRequest(
        entities=entities or None,
        product_types=product_types or None,
    )

    result = get_historic_uc.execute(query)
    return jsonify({"entries": result.entries}), 200
