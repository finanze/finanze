import json
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from dateutil.tz import tzlocal, UTC

from application.ports.template_processor_port import TemplateProcessorPort
from domain.dezimal import Dezimal
from domain.entity import Entity, Feature
from domain.export import NumberFormat, TemplatedDataProcessorParams
from domain.global_position import ProductType
from domain.template import (
    EffectiveTemplatedField,
    ProcessorDataFilter,
    Template,
    TemplatedField,
    get_effective_field,
)
from domain.template_fields import ENTITY, PRODUCT_TYPE, TEMPLATE_FIELD_MATRIX
from domain.template_type import TemplateType

ENTITY_COLUMN = ENTITY.field
PRODUCT_TYPE_COLUMN = PRODUCT_TYPE.field


def _format_type_name(value: Any):
    tokens = value.split(".")
    if len(tokens) >= 2:
        return tokens[-2].upper()
    else:
        return value.upper()


def _format_field_value(value: Any, params: TemplatedDataProcessorParams):
    if value is None:
        return ""

    if isinstance(value, date) and not isinstance(value, datetime):
        date_format = params.date_format
        if not date_format:
            return value.isoformat()
        return value.strftime(date_format)

    elif isinstance(value, datetime):
        datetime_format = params.datetime_format
        value = value.replace(tzinfo=UTC).astimezone(tzlocal())
        if not datetime_format:
            return value.isoformat()
        return value.strftime(datetime_format)

    elif isinstance(value, dict) or isinstance(value, list):
        return json.dumps(value, default=str)

    elif isinstance(value, Dezimal) or isinstance(value, float):
        number_format = params.number_format
        if number_format == NumberFormat.EUROPEAN:
            return str(value).replace(".", ",")

        return str(value)

    elif isinstance(value, UUID):
        return str(value)

    elif isinstance(value, Enum):
        return value.value

    return value


def _generate_default_template(
    feature: Feature, products: Optional[list[ProductType]]
) -> Template:
    fields_set = set()
    fields = []
    feature_products = TEMPLATE_FIELD_MATRIX[feature]
    for product_type in feature_products:
        if not products or not product_type or (products and product_type in products):
            if products:
                feature_fields = feature_products[product_type]
            else:
                feature_fields = list(feature_products.values())
                feature_fields = [
                    item for sublist in feature_fields for item in sublist
                ]

            for specific_field in feature_fields:
                if specific_field.field not in fields_set:
                    fields_set.add(specific_field.field)
                    fields.append(
                        TemplatedField(
                            field=specific_field.field, name=specific_field.field
                        )
                    )

    return Template(
        id=None,
        name="",
        feature=feature,
        type=TemplateType.EXPORT,
        fields=fields,
        products=products,
    )


def _update_products_as_filter(params: TemplatedDataProcessorParams):
    if not params.filters:
        params.filters = []

    if params.products:
        params.filters.append(
            ProcessorDataFilter(
                field="product_type",
                values=[product.value for product in params.products],
            )
        )


class TemplatedDataGenerator(TemplateProcessorPort):
    async def process(
        self, data: list, params: TemplatedDataProcessorParams
    ) -> list[list[str]]:
        if not params.template:
            params.template = _generate_default_template(
                params.feature, params.products
            )

        params.template.fields = [
            get_effective_field(
                field.field,
                field.name or field.field,
                field.default_value,
                params.template,
            )
            for field in params.template.fields
        ]

        rows = [[field.name for field in params.template.fields]]
        rows += self._map_rows(data, params)

        return rows

    def _map_rows(
        self, data: list, params: TemplatedDataProcessorParams
    ) -> list[list[str]]:
        template = params.template
        if template.feature == Feature.POSITION:
            field_paths = []
            for product in params.products:
                if product == ProductType.CROWDLENDING.value:
                    field_paths.append(f"products.{product.value}")
                else:
                    field_paths.append(f"products.{product.value}.entries")

            for entry in data:
                if ProductType.CRYPTO in params.products:
                    crypto_pos = entry.products[ProductType.CRYPTO]
                    crypto_wallets = crypto_pos.entries
                    crypto_pos.entries = []
                    for wallet in crypto_wallets:
                        crypto_pos.entries.extend(wallet.assets)

            return self._map_entries(data, params, field_paths)

        elif template.feature == Feature.AUTO_CONTRIBUTIONS:
            return self._map_entries(data, params, ["periodic"])

        elif template.feature in (Feature.TRANSACTIONS, Feature.HISTORIC):
            _update_products_as_filter(params)
            return self._map_entries(data, params)

        else:
            raise ValueError()

    def _map_entries(
        self,
        data: list,
        params: TemplatedDataProcessorParams,
        field_paths: list[str] = [""],
    ) -> list[list[str]]:
        columns = []
        for field in params.template.fields:
            columns.append(field)

        product_rows = []
        for entry in data:
            for field_path in field_paths:
                try:
                    entity = None
                    path_tokens = field_path.split(".")
                    target_data = entry
                    if path_tokens and path_tokens[0]:
                        for field in path_tokens:
                            if hasattr(target_data, ENTITY_COLUMN):
                                entity = target_data.entity
                            try:
                                target_data = getattr(target_data, field)
                            except AttributeError:
                                target_data = target_data.get(field)

                    if not target_data:
                        continue

                    if isinstance(target_data, list):
                        for product in target_data:
                            if not self._matches_filters(product, params):
                                continue
                            product_rows.append(
                                self._map_row(
                                    product, field_path, columns, params, entity=entity
                                )
                            )
                    else:
                        if not self._matches_filters(target_data, params):
                            continue
                        product_rows.append(
                            self._map_row(
                                target_data, field_path, columns, params, entity=entity
                            )
                        )
                except AttributeError:
                    pass

        return product_rows

    @staticmethod
    def _matches_filters(element: Any, config: TemplatedDataProcessorParams):
        filters = config.filters or []
        for filter_rule in filters:
            filtered_field = filter_rule.field
            matching_values = filter_rule.values
            matching_values = (
                [matching_values]
                if not isinstance(matching_values, list)
                else matching_values
            )
            matching_values = [
                str(value.value) if isinstance(value, Enum) else str(value)
                for value in matching_values
            ]
            value = (
                str(getattr(element, filtered_field).value)
                if isinstance(getattr(element, filtered_field), Enum)
                else str(getattr(element, filtered_field))
            )
            if value not in matching_values:
                return False
        return True

    @staticmethod
    def _map_row(
        element: Any,
        field_path: str,
        columns: list[EffectiveTemplatedField],
        config: TemplatedDataProcessorParams,
        entity: Entity = None,
    ) -> list[str]:
        rows = []
        element = asdict(element)
        if ENTITY_COLUMN not in element:
            element[ENTITY_COLUMN] = str(entity)
        else:
            element[ENTITY_COLUMN] = element[ENTITY_COLUMN]["name"]

        if PRODUCT_TYPE_COLUMN not in element:
            element[PRODUCT_TYPE_COLUMN] = _format_type_name(field_path)

        for column in columns:
            column_name = column.field
            if column_name in element:
                rows.append(_format_field_value(element[column_name], config))
            else:
                complex_column = "." in column_name
                if complex_column:
                    fields = column_name.split(".")
                    obj = element
                    for field in fields:
                        obj = obj.get(field) or {}
                    value = _format_field_value(obj, config) if obj != {} else ""
                    rows.append(value)
                else:
                    rows.append("")

        return rows
