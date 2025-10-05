from uuid import UUID

from domain.exception.exceptions import (
    MissingFieldsError,
    RelatedAccountNotFound,
    RelatedFundPortfolioNotFound,
    EntityNameAlreadyExists,
    EntityNotFound,
)
from domain.global_position import UpdatePositionRequest
from domain.use_cases.update_position import UpdatePosition
from flask import jsonify, request
from infrastructure.controller.mappers.manual_position_mapper import map_manual_products


async def update_position(update_position_uc: UpdatePosition):
    body = request.json
    if not isinstance(body, dict):
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Expected a JSON object"}
        ), 400

    try:
        raw_products = body.get("products", {})
        products = map_manual_products(raw_products)
        entity_id = None
        entity_id_raw = body.get("entity_id")
        if entity_id_raw:
            entity_id = UUID(entity_id_raw)
        new_entity_name = body.get("new_entity_name")
        if not entity_id and not new_entity_name:
            raise MissingFieldsError(["entity_id", "new_entity_name"])
    except MissingFieldsError as mfe:
        return jsonify({"code": "MISSING_FIELDS", "missing": mfe.missing_fields}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    req = UpdatePositionRequest(
        entity_id=entity_id, new_entity_name=new_entity_name, products=products
    )
    try:
        await update_position_uc.execute(req)
    except EntityNameAlreadyExists as e:
        return jsonify({"code": "CONFLICT", "message": str(e)}), 409
    except EntityNotFound:
        return jsonify({"code": "NOT_FOUND", "message": "Entity not found"}), 404
    except (RelatedAccountNotFound, RelatedFundPortfolioNotFound) as e:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": str(e)}),
            400,
        )

    return "", 204
