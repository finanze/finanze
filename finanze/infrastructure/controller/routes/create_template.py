from domain.exception.exceptions import TemplateAlreadyExists
from domain.use_cases.create_template import CreateTemplate
from flask import jsonify, request
from infrastructure.controller.mappers.template_mapper import map_template


def create_template(create_template_uc: CreateTemplate):
    body = request.json or {}
    try:
        template = map_template(body)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        create_template_uc.execute(template)
    except TemplateAlreadyExists as e:
        return jsonify({"code": "TEMPLATE_ALREADY_EXISTS", "message": str(e)}), 409

    return "", 204
