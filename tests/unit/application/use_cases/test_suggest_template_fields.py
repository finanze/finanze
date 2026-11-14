from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.ports.file_rw_port import TableRWPort
from application.ports.template_parser_port import TemplateParserPort
from application.ports.template_port import TemplatePort
from application.use_cases.suggest_template_fields import SuggestTemplateFieldsImpl
from domain.entity import Feature
from domain.exception.exceptions import FeatureNotSupported, UnsupportedFileFormat
from domain.file_upload import FileUpload
from domain.global_position import ProductType
from domain.importing import (
    SuggestedTemplateField,
    TemplateFieldsSuggestion,
    TemplateFieldsSuggestionRequest,
)
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType


def _request(feature=Feature.TRANSACTIONS, product=ProductType.ACCOUNT):
    return TemplateFieldsSuggestionRequest(
        file=FileUpload(
            filename="movements.csv",
            content_type="text/csv",
            content_length=0,
            data=BytesIO(b""),
        ),
        feature=feature,
        product=product,
    )


def _template(feature=Feature.TRANSACTIONS, products=None):
    return Template(
        id=uuid4(),
        name=f"Template {feature.value} {products}",
        feature=feature,
        type=TemplateType.IMPORT,
        fields=[TemplatedField(field="date", name="Fecha")],
        products=products,
    )


def _use_case(table=None, suggestion=None, templates=None):
    table_rw = MagicMock(spec=TableRWPort)
    table_rw.parse = AsyncMock(return_value=table or [["Fecha"]])
    parser = MagicMock(spec=TemplateParserPort)
    parser.suggest_fields = AsyncMock(
        return_value=suggestion
        or TemplateFieldsSuggestion(
            headers=["Fecha"],
            fields=[SuggestedTemplateField(field="date", name="Fecha")],
        )
    )
    template_port = MagicMock(spec=TemplatePort)
    template_port.get_by_type = AsyncMock(return_value=templates or [])
    return (
        SuggestTemplateFieldsImpl(table_rw, parser, template_port),
        table_rw,
        parser,
    )


class TestSuggestTemplateFields:
    @pytest.mark.asyncio
    async def test_suggests_with_importable_fields_of_product(self):
        use_case, table_rw, parser = _use_case()
        request = _request()

        result = await use_case.execute(request)

        assert result.fields == [SuggestedTemplateField(field="date", name="Fecha")]
        table_rw.parse.assert_awaited_once_with(request.file)
        table, fields, templates = parser.suggest_fields.await_args.args
        assert table == [["Fecha"]]
        assert templates == []
        field_names = [field.field for field in fields]
        assert {"date", "name", "amount", "currency"} <= set(field_names)
        assert "product_type" not in field_names

    @pytest.mark.asyncio
    async def test_matches_only_templates_of_feature_and_product(self):
        any_product = _template()
        empty_products = _template(products=[])
        account = _template(products=[ProductType.ACCOUNT, ProductType.CRYPTO])
        crypto = _template(products=[ProductType.CRYPTO])
        positions = _template(Feature.POSITION, [ProductType.ACCOUNT])
        use_case, _, parser = _use_case(
            templates=[any_product, empty_products, account, crypto, positions]
        )

        await use_case.execute(_request())

        _, _, templates = parser.suggest_fields.await_args.args
        assert templates == [any_product, empty_products, account]

    @pytest.mark.parametrize(
        "feature,product",
        [
            (Feature.HISTORIC, ProductType.STOCK_ETF),
            (Feature.TRANSACTIONS, ProductType.CROWDLENDING),
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_non_importable_combinations(self, feature, product):
        use_case, table_rw, _ = _use_case()

        with pytest.raises(FeatureNotSupported):
            await use_case.execute(_request(feature, product))

        table_rw.parse.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_propagates_unsupported_files(self):
        use_case, table_rw, parser = _use_case()
        table_rw.parse.side_effect = UnsupportedFileFormat("Unsupported")

        with pytest.raises(UnsupportedFileFormat):
            await use_case.execute(_request())

        parser.suggest_fields.assert_not_awaited()
