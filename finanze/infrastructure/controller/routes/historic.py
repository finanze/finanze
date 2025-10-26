from uuid import UUID
from domain.historic import HistoricQueryRequest
from domain.use_cases.get_historic import GetHistoric
from flask import jsonify, request
from domain.global_position import ProductType


def get_historic(get_historic_uc: GetHistoric):
    raw_entities = request.args.getlist("entity")
    raw_excluded_entities = request.args.getlist("excluded_entity")
    raw_product_types = request.args.getlist("product_type")

    entities = []
    excluded_entities = []
    product_types = []

    for e in raw_entities:
        try:
            entities.append(UUID(e))
        except ValueError:
            return jsonify({"error": f"Invalid entity UUID: {e}"}), 400
    for e in raw_excluded_entities:
        try:
            excluded_entities.append(UUID(e))
        except ValueError:
            return jsonify({"error": f"Invalid excluded_entity UUID: {e}"}), 400

    for pt in raw_product_types:
        try:
            product_types.append(ProductType(pt))
        except ValueError:
            return jsonify({"error": f"Invalid product_type: {pt}"}), 400

    query = HistoricQueryRequest(
        entities=entities or None,
        excluded_entities=excluded_entities or None,
        product_types=product_types or None,
    )

    result = get_historic_uc.execute(query)
    return jsonify({"entries": result.entries}), 200
