from typing import Any, Optional
from uuid import UUID

from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.exception.exceptions import InvalidTemplateDefaultValue
from domain.global_position import ProductType
from domain.template_fields import (
    TEMPLATE_FIELD_MATRIX,
    TemplateFieldType,
)
from domain.template_type import TemplateType
from pydantic.dataclasses import dataclass


@dataclass
class TemplatedField:
    field: str
    name: Optional[str]
    default_value: Optional[Any] = None


@dataclass
class EffectiveTemplatedField:
    field: str
    type: TemplateFieldType
    name: Optional[str]
    required: bool
    values: Optional[list[str]] = None
    default_value: Optional[Any] = None


@dataclass
class Template:
    id: Optional[UUID]
    name: str
    feature: Feature
    type: TemplateType
    fields: list[TemplatedField | EffectiveTemplatedField]
    products: Optional[list[ProductType]]


@dataclass
class ProcessorDataFilter:
    field: str
    values: str | list[str]


def get_effective_field(
    field: str, custom_name: Optional[str], default: Optional[Any], template: Template
) -> Optional[EffectiveTemplatedField]:
    fields = set()
    feature_products = TEMPLATE_FIELD_MATRIX[template.feature]
    for product_type in feature_products:
        if (
            not product_type
            or not template.products
            or product_type in template.products
        ):
            feature_fields = feature_products[product_type]
            for specific_field in feature_fields:
                if specific_field.field == field:
                    fields.add(specific_field)

    if not fields:
        return None

    fields = list(fields)

    effective_type = next(
        (
            field_type
            for field_type in [
                TemplateFieldType.TEXT,
                TemplateFieldType.ENUM,
                TemplateFieldType.CURRENCY,
                TemplateFieldType.DECIMAL,
                TemplateFieldType.INTEGER,
                TemplateFieldType.DATETIME,
                TemplateFieldType.DATE,
            ]
            if any(f.type == field_type for f in fields)
        ),
        TemplateFieldType.BOOLEAN,
    )

    values = None
    if effective_type == TemplateFieldType.ENUM:
        enum_values = set()
        for f in fields:
            if f.type == TemplateFieldType.ENUM and f.enum is not None:
                enum_values.update([e.value for e in f.enum])
        values = sorted(enum_values)

    field_name = fields[0].field
    default_value = default or next(
        (f.default_value for f in fields if f.default_value is not None), None
    )
    required = any(f.required for f in fields)
    return EffectiveTemplatedField(
        field=field_name,
        type=effective_type,
        values=values,
        name=custom_name,
        default_value=default_value,
        required=required,
    )


def validate_template_default_values(template: Template):
    for templated_field in template.fields:
        if templated_field.default_value is None:
            continue

        effective_field = get_effective_field(
            templated_field.field,
            templated_field.name,
            templated_field.default_value,
            template,
        )

        if effective_field is None:
            continue

        field_display_name = templated_field.name or templated_field.field
        default_value = templated_field.default_value

        # DATE and DATETIME are not supported
        if effective_field.type in (TemplateFieldType.DATE, TemplateFieldType.DATETIME):
            raise InvalidTemplateDefaultValue(
                field_display_name,
                effective_field.type.value,
                "Default values for DATE and DATETIME types are not supported",
            )

        # Validate BOOLEAN first (before other type checks) to prevent Dezimal from parsing booleans as integers
        if effective_field.type == TemplateFieldType.BOOLEAN:
            if not isinstance(default_value, bool):
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not a valid boolean",
                )

        # Validate ENUM
        if effective_field.type == TemplateFieldType.ENUM:
            if effective_field.values is None:
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    "ENUM field has no valid values defined",
                )
            if str(default_value) not in effective_field.values:
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not in allowed values: {', '.join(effective_field.values)}",
                )

        # Validate INTEGER
        elif effective_field.type == TemplateFieldType.INTEGER:
            if isinstance(default_value, bool):
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not a valid integer",
                )
            try:
                int_val = int(default_value)
                # Check if it's actually an integer (not a float)
                if isinstance(default_value, float) and default_value != int_val:
                    raise ValueError()
            except (ValueError, TypeError):
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not a valid integer",
                )

        # Validate DECIMAL
        elif effective_field.type == TemplateFieldType.DECIMAL:
            if isinstance(default_value, bool):
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not a valid decimal",
                )
            try:
                Dezimal(default_value)
            except (ValueError, TypeError):
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not a valid decimal",
                )

        # Validate CURRENCY
        elif effective_field.type == TemplateFieldType.CURRENCY:
            currency_str = str(default_value).upper()
            if currency_str not in CURRENCY_SYMBOL_MAP:
                raise InvalidTemplateDefaultValue(
                    field_display_name,
                    effective_field.type.value,
                    f"Value '{default_value}' is not a valid ISO currency code",
                )

        # TEXT - any string is valid, no validation needed
