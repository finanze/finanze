from uuid import UUID

from domain.use_cases.update_template import UpdateTemplate
from flask import jsonify, request
from infrastructure.controller.mappers.template_mapper import map_template


def update_template(update_template_uc: UpdateTemplate):
    body = request.json or {}
    try:
        template_id = UUID(body["id"])
        template = map_template(body, template_id=template_id)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    update_template_uc.execute(template)
    return "", 204
