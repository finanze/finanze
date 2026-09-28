import pytest

from domain.entity import Feature
from domain.export import NumberFormat, TemplatedDataProcessorParams
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.importing import (
    ImportCandidate,
    ImportErrorType,
    TemplatedDataParserParams,
)
from domain.template import Template, TemplatedField
from domain.template_fields import TEMPLATE_FIELD_MATRIX
from domain.template_type import TemplateType
from domain.transactions import TxType
from infrastructure.templating.templated_data_generator import TemplatedDataGenerator
from infrastructure.templating.templated_data_parser import TemplateDataParser


def _candidate(
    transaction_type,
    *,
    amount="",
    shares="",
    price="",
    ratio="",
    isin="ES0105046009",
    ticker="",
):
    product = ProductType.STOCK_ETF
    headers = [
        field.field for field in TEMPLATE_FIELD_MATRIX[Feature.TRANSACTIONS][product]
    ]
    values = {
        "ref": "split-ref",
        "name": "Example stock",
        "amount": amount,
        "currency": "EUR",
        "type": transaction_type,
        "date": "2025-06-19T12:00:00",
        "isin": isin,
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "fees": "",
        "retentions": "",
        "split_ratio": ratio,
    }
    template = Template(
        id=None,
        name="",
        feature=Feature.TRANSACTIONS,
        type=TemplateType.IMPORT,
        fields=[TemplatedField(field=header, name=header) for header in headers],
        products=[product],
    )
    params = TemplatedDataParserParams(
        template=template,
        number_format=NumberFormat.ENGLISH,
        feature=Feature.TRANSACTIONS,
        product=product,
        datetime_format=None,
        date_format=None,
        params={"entity": "Broker"},
    )
    return ImportCandidate(
        name="transactions.csv",
        source=DataSource.MANUAL,
        params=params,
        data=[headers, [values.get(header, "") for header in headers]],
    )


class TestTemplatedDataParser:
    @pytest.mark.asyncio
    async def test_imports_split_with_blank_amount_price_and_shares(self):
        result = await TemplateDataParser().transactions(
            [_candidate(TxType.SPLIT.value, ratio="2")], {}
        )

        assert result.errors == []
        transaction = result.transactions.investment[0]
        assert transaction.type == TxType.SPLIT
        assert transaction.amount == 0
        assert transaction.price == 0
        assert transaction.shares is None
        assert transaction.split_ratio == 2

    @pytest.mark.asyncio
    async def test_buy_still_requires_amount_shares_and_price(self):
        result = await TemplateDataParser().transactions(
            [_candidate(TxType.BUY.value)], {}
        )

        missing = {
            field["field"]
            for error in result.errors
            if error.type == ImportErrorType.MISSING_FIELD
            for field in error.detail
        }
        assert {"amount", "shares", "price"} <= missing
        assert not result.transactions.investment

    @pytest.mark.asyncio
    async def test_split_ratio_exports_and_remains_blank_on_buy(self):
        parser = TemplateDataParser()
        split_result = await parser.transactions(
            [_candidate(TxType.SPLIT.value, ratio="2")], {}
        )
        buy_result = await parser.transactions(
            [_candidate(TxType.BUY.value, amount="100", shares="2", price="50")],
            {},
        )
        processor_params = TemplatedDataProcessorParams(
            template=None,
            number_format=NumberFormat.ENGLISH,
            feature=Feature.TRANSACTIONS,
            products=[ProductType.STOCK_ETF],
            datetime_format=None,
            date_format=None,
        )

        rows = await TemplatedDataGenerator().process(
            [
                split_result.transactions.investment[0],
                buy_result.transactions.investment[0],
            ],
            processor_params,
        )

        ratio_index = rows[0].index("split_ratio")
        assert rows[1][ratio_index] == "2"
        assert rows[2][ratio_index] == ""

    @pytest.mark.asyncio
    async def test_cash_in_lieu_requires_positive_price(self):
        result = await TemplateDataParser().transactions(
            [_candidate(TxType.SPLIT.value, amount="25", ratio="2")], {}
        )

        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert result.errors[0].detail[0]["field"] == "price"
        assert not result.transactions.investment

    @pytest.mark.asyncio
    async def test_split_requires_stock_identity(self):
        result = await TemplateDataParser().transactions(
            [_candidate(TxType.SPLIT.value, ratio="2", isin="")], {}
        )

        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert result.errors[0].detail == ["isin", "ticker"]
        assert not result.transactions.investment
