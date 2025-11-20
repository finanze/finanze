from typing import Optional
from uuid import UUID

from domain.entity import Feature
from domain.global_position import ProductType
from domain.template import Template, TemplatedField
from domain.template_fields import (
    FIELDS_BY_NAME,
)
from domain.template_type import TemplateType


def map_template(body: dict, template_id: Optional[UUID] = None) -> Template:
    name = body["name"]

    feature_value = body["feature"]
    try:
        feature = Feature(feature_value)
    except ValueError:
        valid_features = [f.value for f in Feature]
        raise ValueError(
            f"Invalid feature '{feature_value}'. Valid values: {', '.join(valid_features)}"
        )

    type_value = body["type"]
    try:
        template_type = TemplateType(type_value)
    except ValueError:
        valid_types = [t.value for t in TemplateType]
        raise ValueError(
            f"Invalid type '{type_value}'. Valid values: {', '.join(valid_types)}"
        )

    fields_payload = body.get("fields", [])
    templated_fields: list[TemplatedField] = []
    for f in fields_payload:
        field = f.get("field")
        if not field:
            raise ValueError("Field missing 'field' property")

        field_def = FIELDS_BY_NAME.get(field)
        if field_def is None:
            raise ValueError(f"Unknown field key: {field}")

        templated_fields.append(
            TemplatedField(
                field=field_def[0].field,
                name=f.get("custom_name"),
                default_value=f.get("default"),
            )
        )

    products_payload = body.get("products")
    products = None
    if products_payload:
        products = []
        for p in products_payload:
            try:
                products.append(ProductType(p))
            except ValueError:
                raise ValueError(f"Invalid product type: {p}")

    return Template(
        id=template_id,
        name=name,
        feature=feature,
        type=template_type,
        fields=templated_fields,
        products=products,
    )
