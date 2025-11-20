from domain.template_fields import TemplateFieldType
from domain.use_cases.get_template_fields import GetTemplateFields
from flask import jsonify


def _serialize_template_field(field):
    data = {
        "key": field.key,
        "field": field.field,
        "type": field.type.value,
        "required": field.required,
        "disabled_default": field.disabled_default,
    }
    if field.type == TemplateFieldType.ENUM and field.enum is not None:
        data["enum_values"] = [e.value for e in field.enum]
    if field.or_requires:
        data["or_requires"] = [req.field for req in field.or_requires]
    if field.template_type:
        data["template_type"] = field.template_type.value
    if field.default_value:
        data["default"] = field.default_value
    return data


def get_template_fields(get_template_fields_uc: GetTemplateFields):
    all_fields = get_template_fields_uc.execute()

    result = {}
    for feature, field_groups in all_fields.items():
        result[feature.value] = [
            {
                "feature": group.feature.value,
                "product": group.product.value if group.product else None,
                "fields": [_serialize_template_field(field) for field in group.fields],
                "template_type": group.template_type.value
                if group.template_type
                else None,
            }
            for group in field_groups
        ]

    return jsonify(result), 200
