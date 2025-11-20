from domain.template_fields import TemplateFieldType
from domain.template_type import TemplateType
from domain.use_cases.get_templates import GetTemplates
from flask import jsonify, request


def _serialize_field(field):
    data = {
        "field": field.field,
        "name": field.name,
        "type": field.type.value,
    }
    if field.type == TemplateFieldType.ENUM and field.values is not None:
        data["enum_values"] = list(field.values)
    if field.default_value is not None:
        data["default"] = field.default_value
    return data


def get_templates(get_templates_uc: GetTemplates):
    template_type_raw = request.args.get("type")
    if not template_type_raw:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Missing type parameter"}
        ), 400
    try:
        template_type = TemplateType(template_type_raw)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid template type"}
        ), 400

    templates = get_templates_uc.execute(template_type)
    return jsonify(
        [
            {
                "id": str(t.id),
                "name": t.name,
                "feature": t.feature.value,
                "type": t.type.value,
                "fields": [_serialize_field(f) for f in t.fields],
                "products": [p.value for p in t.products] if t.products else None,
            }
            for t in templates
        ]
    ), 200
