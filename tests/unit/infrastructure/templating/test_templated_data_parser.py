from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal, tzoffset

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.export import NumberFormat, TemplatedDataProcessorParams
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.importing import (
    ImportCandidate,
    ImportErrorType,
    ImportRowOrigin,
    TemplatedDataParserParams,
)
from domain.template import Template, TemplatedField
from domain.template_fields import TEMPLATE_FIELD_MATRIX
from domain.template_type import TemplateType
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    FundPortfolioTx,
    Transactions,
    TxType,
)
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
    async def test_buy_still_requires_amount_and_shares(self):
        result = await TemplateDataParser().transactions(
            [_candidate(TxType.BUY.value)], {}
        )

        missing = {
            field["field"]
            for error in result.errors
            if error.type == ImportErrorType.MISSING_FIELD
            for field in error.detail
        }
        assert {"amount", "shares"} <= missing
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


DATE = "2025-03-01T09:00:00"
IBAN = "ES9121000418450200051332"


def _headers(product, exclude=()):
    return [
        field.field
        for field in TEMPLATE_FIELD_MATRIX[Feature.TRANSACTIONS][product]
        if field.field not in exclude
    ]


def _tx_candidate(
    product,
    rows,
    *,
    headers=None,
    params=None,
    name="transactions.csv",
    number_format=NumberFormat.ENGLISH,
):
    headers = headers or _headers(product)
    template = Template(
        id=None,
        name="",
        feature=Feature.TRANSACTIONS,
        type=TemplateType.IMPORT,
        fields=[TemplatedField(field=header, name=header) for header in headers],
        products=[product],
    )
    parser_params = TemplatedDataParserParams(
        template=template,
        number_format=number_format,
        feature=Feature.TRANSACTIONS,
        product=product,
        datetime_format=None,
        date_format=None,
        params={"entity": "Bank"} if params is None else params,
    )
    return ImportCandidate(
        name=name,
        source=DataSource.MANUAL,
        params=parser_params,
        data=[headers] + [[row.get(header, "") for header in headers] for row in rows],
    )


def _account_row(**overrides):
    row = {
        "ref": "acc-1",
        "name": "Salary",
        "amount": "1500",
        "currency": "EUR",
        "date": DATE,
    }
    row.update(overrides)
    return row


def _crypto_row(**overrides):
    row = {
        "ref": "cr-1",
        "name": "Bitcoin",
        "amount": "500",
        "currency": "EUR",
        "type": "BUY",
        "date": DATE,
        "symbol": "BTC",
        "currency_amount": "0.005",
        "price": "100000",
        "fees": "1.5",
    }
    row.update(overrides)
    return row


def _portfolio_row(**overrides):
    row = {
        "ref": "fp-1",
        "name": "Custody fee",
        "amount": "12.5",
        "currency": "EUR",
        "type": "FEE",
        "date": DATE,
        "portfolio_name": "Main portfolio",
    }
    row.update(overrides)
    return row


def _entity(name, entity_type=EntityType.FINANCIAL_INSTITUTION):
    return Entity(
        id=uuid4(),
        name=name,
        natural_id=None,
        type=entity_type,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


async def _parse(product, rows, existing=None, **kwargs):
    return await TemplateDataParser().transactions(
        [_tx_candidate(product, rows, **kwargs)], existing or {}
    )


def _error_fields(error):
    return [item["field"] if isinstance(item, dict) else item for item in error.detail]


class TestAccountTransactionsImport:
    @pytest.mark.asyncio
    async def test_imports_inflow_with_defaults(self):
        row = _account_row()
        result = await _parse(ProductType.ACCOUNT, [row])

        assert result.errors == []
        assert result.transactions.investment == []
        tx = result.transactions.account[0]
        assert isinstance(tx, AccountTx)
        assert tx.product_type == ProductType.ACCOUNT
        assert tx.type == TxType.INFLOW
        assert tx.amount == Dezimal(1500)
        assert tx.fees == Dezimal(0)
        assert tx.retentions == Dezimal(0)
        assert tx.net_amount == Dezimal(1500)
        assert tx.source == DataSource.MANUAL
        assert tx.entity.name == "Bank"
        assert tx.entity.type == EntityType.FINANCIAL_INSTITUTION
        assert result.created_entities == {tx.entity}
        headers = _headers(ProductType.ACCOUNT)
        assert result.origins[tx.id] == ImportRowOrigin(
            entry="transactions.csv",
            row=[row.get(header, "") for header in headers],
        )

    @pytest.mark.asyncio
    async def test_negative_amount_becomes_unsigned_outflow(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row(amount="-80.25", fees="-1", retentions="-0.5")],
        )

        assert result.errors == []
        tx = result.transactions.account[0]
        assert tx.type == TxType.OUTFLOW
        assert tx.amount == Dezimal("80.25")
        assert tx.fees == Dezimal(1)
        assert tx.retentions == Dezimal("0.5")
        assert tx.net_amount == Dezimal("81.75")

    @pytest.mark.parametrize(
        "tx_type, amount, expected_type, expected_amount",
        [
            ("OUTFLOW", "20", TxType.OUTFLOW, "20"),
            ("INFLOW", "-20", TxType.OUTFLOW, "20"),
            ("fee", "-3", TxType.FEE, "3"),
            ("FEE", "3", TxType.FEE, "3"),
            ("INTEREST", "-0.7", TxType.INTEREST, "0.7"),
            ("OUTFLOW", "0", TxType.OUTFLOW, "0"),
        ],
    )
    @pytest.mark.asyncio
    async def test_explicit_type_and_sign_matrix(
        self, tx_type, amount, expected_type, expected_amount
    ):
        result = await _parse(
            ProductType.ACCOUNT, [_account_row(type=tx_type, amount=amount)]
        )

        assert result.errors == []
        tx = result.transactions.account[0]
        assert tx.type == expected_type
        assert tx.amount == Dezimal(expected_amount)

    @pytest.mark.asyncio
    async def test_imports_without_type_column(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row(amount="-10"), _account_row(ref="acc-2", amount="10")],
            headers=_headers(ProductType.ACCOUNT, exclude=("type",)),
        )

        assert result.errors == []
        assert [tx.type for tx in result.transactions.account] == [
            TxType.OUTFLOW,
            TxType.INFLOW,
        ]

    @pytest.mark.asyncio
    async def test_imports_without_fee_and_retention_columns(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row()],
            headers=["ref", "name", "amount", "currency", "date"],
        )

        assert result.errors == []
        tx = result.transactions.account[0]
        assert tx.fees == Dezimal(0)
        assert tx.retentions == Dezimal(0)
        assert tx.net_amount == Dezimal(1500)

    @pytest.mark.asyncio
    async def test_normalizes_iban_and_counterparty(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [
                _account_row(
                    iban=" es91 2100 0418 4502 0005 1332 ",
                    counterparty="  ACME Corp  ",
                ),
                _account_row(ref="acc-2", counterparty="   "),
            ],
        )

        assert result.errors == []
        first, second = result.transactions.account
        assert first.iban == IBAN
        assert first.counterparty == "ACME Corp"
        assert second.iban is None
        assert second.counterparty is None

    @pytest.mark.asyncio
    async def test_keeps_explicit_net_amount_and_signed_rate_fields(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [
                _account_row(
                    type="INTEREST",
                    amount="10",
                    fees="1",
                    net_amount="-7.5",
                    interest_rate="-0.005",
                    avg_balance="-1200",
                )
            ],
        )

        assert result.errors == []
        tx = result.transactions.account[0]
        assert tx.net_amount == Dezimal("7.5")
        assert tx.interest_rate == Dezimal("-0.005")
        assert tx.avg_balance == Dezimal("-1200")

    @pytest.mark.asyncio
    async def test_parses_european_number_format(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row(amount="-1.234,56")],
            number_format=NumberFormat.EUROPEAN,
        )

        assert result.errors == []
        tx = result.transactions.account[0]
        assert tx.type == TxType.OUTFLOW
        assert tx.amount == Dezimal("1234.56")

    @pytest.mark.asyncio
    async def test_naive_dates_become_local_and_offsets_are_kept(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [
                _account_row(),
                _account_row(ref="acc-2", date="2025-03-01T09:00:00+02:00"),
            ],
        )

        assert result.errors == []
        naive, explicit = result.transactions.account
        assert naive.date == datetime(2025, 3, 1, 9, 0, tzinfo=tzlocal())
        assert explicit.date.utcoffset() == timedelta(hours=2)
        assert explicit.date == datetime(2025, 3, 1, 7, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_reuses_existing_entity_and_row_entity_overrides_param(self):
        bank = _entity("Bank")
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row(), _account_row(ref="acc-2", entity="Other Bank")],
            existing={"Bank": bank},
        )

        assert result.errors == []
        first, second = result.transactions.account
        assert first.entity is bank
        assert second.entity.name == "Other Bank"
        assert result.created_entities == {second.entity}

    @pytest.mark.asyncio
    async def test_creates_each_new_entity_once(self):
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row(), _account_row(ref="acc-2")],
        )

        first, second = result.transactions.account
        assert first.entity is second.entity
        assert len(result.created_entities) == 1

    @pytest.mark.asyncio
    async def test_rejects_zero_amount_without_type(self):
        result = await _parse(ProductType.ACCOUNT, [_account_row(amount="0")])

        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert result.errors[0].detail == ["type"]
        assert result.transactions.account == []

    @pytest.mark.parametrize("tx_type", ["BUY", "SELL", "DIVIDEND", "SPLIT"])
    @pytest.mark.asyncio
    async def test_rejects_types_not_allowed_for_accounts(self, tx_type):
        result = await _parse(ProductType.ACCOUNT, [_account_row(type=tx_type)])

        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert result.errors[0].detail == [{"field": "type", "value": tx_type}]
        assert result.transactions.account == []

    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"iban": "ES91-2100-0418"}, "iban"),
            ({"iban": "ES" + "1" * 40}, "iban"),
            ({"counterparty": "x" * 201}, "counterparty"),
            ({"amount": "abc"}, "amount"),
            ({"date": "not-a-date"}, "date"),
            ({"currency": "ZZZ"}, "currency"),
            ({"type": "UNKNOWN"}, "type"),
            ({"interest_rate": "abc"}, "interest_rate"),
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_invalid_values_with_single_error(self, overrides, field):
        result = await _parse(
            ProductType.ACCOUNT,
            [_account_row(**overrides), _account_row(ref="acc-ok")],
        )

        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert _error_fields(result.errors[0]) == [field]
        assert [tx.ref for tx in result.transactions.account] == ["acc-ok"]

    @pytest.mark.asyncio
    async def test_reports_missing_and_invalid_fields_of_same_row(self):
        result = await _parse(
            ProductType.ACCOUNT, [_account_row(name="", amount="abc")]
        )

        assert {
            (error.type, tuple(_error_fields(error))) for error in result.errors
        } == {
            (ImportErrorType.VALIDATION_ERROR, ("amount",)),
            (ImportErrorType.MISSING_FIELD, ("name",)),
        }
        assert result.transactions.account == []

    @pytest.mark.parametrize("field", ["name", "amount", "currency", "date"])
    @pytest.mark.asyncio
    async def test_rejects_missing_required_fields(self, field):
        result = await _parse(ProductType.ACCOUNT, [_account_row(**{field: ""})])

        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert _error_fields(result.errors[0]) == [field]
        assert result.transactions.account == []

    @pytest.mark.asyncio
    async def test_rejects_rows_without_entity(self):
        result = await _parse(ProductType.ACCOUNT, [_account_row()], params={})

        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert result.errors[0].detail == ["entity"]
        assert result.transactions.account == []
        assert result.created_entities == set()


class TestCryptoTransactionsImport:
    @pytest.mark.asyncio
    async def test_imports_buy(self):
        exchange = _entity("Exchange", EntityType.CRYPTO_EXCHANGE)
        result = await _parse(
            ProductType.CRYPTO,
            [_crypto_row(symbol=" btc ", currency_amount="-0.005")],
            existing={"Exchange": exchange},
            params={"entity": "Exchange"},
        )

        assert result.errors == []
        assert result.transactions.account == []
        tx = result.transactions.investment[0]
        assert isinstance(tx, CryptoCurrencyTx)
        assert tx.product_type == ProductType.CRYPTO
        assert tx.entity is exchange
        assert tx.symbol == "BTC"
        assert tx.currency_amount == Dezimal("0.005")
        assert tx.price == Dezimal(100000)
        assert tx.amount == Dezimal(500)
        assert tx.fees == Dezimal("1.5")
        assert tx.net_amount == Dezimal("501.5")
        assert result.created_entities == set()

    @pytest.mark.parametrize(
        "tx_type, expected_net",
        [("SELL", "498.5"), ("DIVIDEND", "498.5"), ("FEE", "501.5")],
    )
    @pytest.mark.asyncio
    async def test_imports_allowed_types(self, tx_type, expected_net):
        result = await _parse(ProductType.CRYPTO, [_crypto_row(type=tx_type)])

        assert result.errors == []
        tx = result.transactions.investment[0]
        assert tx.type == TxType(tx_type)
        assert tx.net_amount == Dezimal(expected_net)

    @pytest.mark.asyncio
    async def test_imports_without_fee_columns(self):
        result = await _parse(
            ProductType.CRYPTO,
            [_crypto_row()],
            headers=_headers(ProductType.CRYPTO, exclude=("fees", "retentions")),
        )

        assert result.errors == []
        tx = result.transactions.investment[0]
        assert tx.fees == Dezimal(0)
        assert tx.net_amount == Dezimal(500)

    @pytest.mark.parametrize(
        "tx_type", ["INFLOW", "OUTFLOW", "SPLIT", "TRANSFER_IN", "SWAP_FROM"]
    )
    @pytest.mark.asyncio
    async def test_rejects_types_not_allowed_for_crypto(self, tx_type):
        result = await _parse(ProductType.CRYPTO, [_crypto_row(type=tx_type)])

        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert result.errors[0].detail == [{"field": "type", "value": tx_type}]
        assert result.transactions.investment == []

    @pytest.mark.parametrize("field", ["type", "symbol", "currency_amount", "amount"])
    @pytest.mark.asyncio
    async def test_rejects_missing_required_fields(self, field):
        result = await _parse(ProductType.CRYPTO, [_crypto_row(**{field: ""})])

        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert _error_fields(result.errors[0]) == [field]
        assert result.transactions.investment == []

    @pytest.mark.asyncio
    async def test_rejects_blank_symbol(self):
        result = await _parse(ProductType.CRYPTO, [_crypto_row(symbol="   ")])

        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert _error_fields(result.errors[0]) == ["symbol"]
        assert result.transactions.investment == []

    @pytest.mark.asyncio
    async def test_rejects_invalid_price(self):
        result = await _parse(ProductType.CRYPTO, [_crypto_row(price="1e")])

        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert _error_fields(result.errors[0]) == ["price"]
        assert result.transactions.investment == []


class TestFundPortfolioTransactionsImport:
    @pytest.mark.asyncio
    async def test_imports_fee(self):
        result = await _parse(
            ProductType.FUND_PORTFOLIO,
            [_portfolio_row(amount="-12.5", iban="es91 2100 0418 4502 0005 1332")],
        )

        assert result.errors == []
        assert result.transactions.account == []
        tx = result.transactions.investment[0]
        assert isinstance(tx, FundPortfolioTx)
        assert tx.product_type == ProductType.FUND_PORTFOLIO
        assert tx.type == TxType.FEE
        assert tx.amount == Dezimal("12.5")
        assert tx.fees == Dezimal(0)
        assert tx.portfolio_name == "Main portfolio"
        assert tx.iban == IBAN

    @pytest.mark.parametrize("tx_type", ["BUY", "SELL", "INFLOW", "INTEREST"])
    @pytest.mark.asyncio
    async def test_rejects_types_other_than_fee(self, tx_type):
        result = await _parse(
            ProductType.FUND_PORTFOLIO, [_portfolio_row(type=tx_type)]
        )

        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert result.errors[0].detail == [{"field": "type", "value": tx_type}]
        assert result.transactions.investment == []

    @pytest.mark.parametrize("field", ["portfolio_name", "type"])
    @pytest.mark.asyncio
    async def test_rejects_missing_required_fields(self, field):
        result = await _parse(
            ProductType.FUND_PORTFOLIO, [_portfolio_row(**{field: ""})]
        )

        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert _error_fields(result.errors[0]) == [field]
        assert result.transactions.investment == []

    @pytest.mark.asyncio
    async def test_rejects_invalid_iban(self):
        result = await _parse(
            ProductType.FUND_PORTFOLIO, [_portfolio_row(iban="ES91#2100")]
        )

        assert result.errors[0].type == ImportErrorType.VALIDATION_ERROR
        assert result.errors[0].detail == [{"field": "iban", "value": "ES91#2100"}]
        assert result.transactions.investment == []


class TestMixedTransactionsImport:
    @pytest.mark.asyncio
    async def test_aggregates_candidates_and_shares_created_entities(self):
        result = await TemplateDataParser().transactions(
            [
                _tx_candidate(ProductType.ACCOUNT, [_account_row()], name="a.csv"),
                _tx_candidate(ProductType.CRYPTO, [_crypto_row()], name="c.csv"),
                _tx_candidate(
                    ProductType.FUND_PORTFOLIO, [_portfolio_row()], name="p.csv"
                ),
            ],
            {},
        )

        assert result.errors == []
        account = result.transactions.account[0]
        crypto, portfolio = result.transactions.investment
        assert account.entity is crypto.entity is portfolio.entity
        assert len(result.created_entities) == 1
        assert {origin.entry for origin in result.origins.values()} == {
            "a.csv",
            "c.csv",
            "p.csv",
        }

    @pytest.mark.asyncio
    async def test_stock_values_are_imported_unsigned(self):
        result = await TemplateDataParser().transactions(
            [_candidate(TxType.BUY.value, amount="-100", shares="-2", price="-50")],
            {},
        )

        assert result.errors == []
        tx = result.transactions.investment[0]
        assert tx.amount == Dezimal(100)
        assert tx.shares == Dezimal(2)
        assert tx.price == Dezimal(50)
        assert tx.net_amount == Dezimal(100)


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class TestTransactionsRoundTrip:
    async def _round_trip(self, product, txs):
        rows = await TemplatedDataGenerator().process(
            txs,
            TemplatedDataProcessorParams(
                template=None,
                number_format=NumberFormat.ENGLISH,
                feature=Feature.TRANSACTIONS,
                products=[product],
                datetime_format=None,
                date_format=None,
            ),
        )
        headers = rows[0]
        candidate = _tx_candidate(
            product,
            [dict(zip(headers, row)) for row in rows[1:]],
            headers=headers,
            params={},
        )
        entity = txs[0].entity
        return await TemplateDataParser().transactions(
            [candidate], {entity.name: entity}
        )

    @pytest.mark.asyncio
    async def test_account_round_trip(self):
        bank = _entity("Bank")
        original = AccountTx(
            id=uuid4(),
            ref="acc-rt",
            name="Rent",
            amount=Dezimal("950.10"),
            currency="EUR",
            type=TxType.OUTFLOW,
            date=_utc(2025, 2, 3, 10, 30),
            entity=bank,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal("1.5"),
            retentions=Dezimal(0),
            interest_rate=Dezimal("0.01"),
            avg_balance=Dezimal("2000"),
            net_amount=Dezimal("951.60"),
            counterparty="Landlord",
            iban=IBAN,
        )

        result = await self._round_trip(ProductType.ACCOUNT, [original])

        assert result.errors == []
        tx = result.transactions.account[0]
        for attr in (
            "ref",
            "name",
            "amount",
            "currency",
            "type",
            "date",
            "fees",
            "retentions",
            "interest_rate",
            "avg_balance",
            "net_amount",
            "counterparty",
            "iban",
        ):
            assert getattr(tx, attr) == getattr(original, attr), attr
        assert tx.entity is bank
        assert tx.source == DataSource.MANUAL

    @pytest.mark.asyncio
    async def test_crypto_round_trip(self):
        exchange = _entity("Exchange", EntityType.CRYPTO_EXCHANGE)
        original = CryptoCurrencyTx(
            id=uuid4(),
            ref="cr-rt",
            name="Ethereum",
            amount=Dezimal("1500"),
            currency="USD",
            type=TxType.SELL,
            date=_utc(2025, 4, 5, 8, 0),
            entity=exchange,
            source=DataSource.REAL,
            product_type=ProductType.CRYPTO,
            currency_amount=Dezimal("0.5"),
            symbol="ETH",
            price=Dezimal("3000"),
            fees=Dezimal("2"),
            retentions=Dezimal(0),
            net_amount=Dezimal("1498"),
            contract_address="0xabc",
            order_date=_utc(2025, 4, 5, 7, 59),
        )

        result = await self._round_trip(ProductType.CRYPTO, [original])

        assert result.errors == []
        tx = result.transactions.investment[0]
        for attr in (
            "ref",
            "name",
            "amount",
            "currency",
            "type",
            "date",
            "currency_amount",
            "symbol",
            "price",
            "fees",
            "net_amount",
            "contract_address",
            "order_date",
        ):
            assert getattr(tx, attr) == getattr(original, attr), attr
        assert tx.entity is exchange

    @pytest.mark.asyncio
    async def test_fund_portfolio_round_trip(self):
        bank = _entity("Bank")
        original = FundPortfolioTx(
            id=uuid4(),
            ref="fp-rt",
            name="Management fee",
            amount=Dezimal("8.25"),
            currency="EUR",
            type=TxType.FEE,
            date=_utc(2025, 6, 30, 0, 0),
            entity=bank,
            source=DataSource.REAL,
            product_type=ProductType.FUND_PORTFOLIO,
            portfolio_name="Robo",
            iban=IBAN,
            fees=Dezimal(0),
        )

        result = await self._round_trip(ProductType.FUND_PORTFOLIO, [original])

        assert result.errors == []
        tx = result.transactions.investment[0]
        for attr in (
            "ref",
            "name",
            "amount",
            "currency",
            "type",
            "date",
            "portfolio_name",
            "iban",
            "fees",
        ):
            assert getattr(tx, attr) == getattr(original, attr), attr
        assert tx.entity is bank

    @pytest.mark.asyncio
    async def test_round_trip_result_fits_transactions_container(self):
        bank = _entity("Bank")
        original = AccountTx(
            id=uuid4(),
            ref="acc-rt",
            name="Deposit",
            amount=Dezimal("10"),
            currency="EUR",
            type=TxType.INFLOW,
            date=_utc(2025, 1, 1, 0, 0),
            entity=bank,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal(0),
            retentions=Dezimal(0),
        )

        result = await self._round_trip(ProductType.ACCOUNT, [original])

        assert isinstance(result.transactions, Transactions)
        assert result.transactions.account[0].net_amount == Dezimal(10)

    @pytest.mark.asyncio
    async def test_round_trip_keeps_instant_of_non_utc_aware_dates(self):
        bank = _entity("Bank")
        late_evening = datetime(2025, 2, 3, 23, 30, tzinfo=tzoffset(None, 5 * 3600))
        original = AccountTx(
            id=uuid4(),
            ref="acc-tz",
            name="Late dinner",
            amount=Dezimal("42"),
            currency="EUR",
            type=TxType.OUTFLOW,
            date=late_evening,
            entity=bank,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal(0),
            retentions=Dezimal(0),
        )

        result = await self._round_trip(ProductType.ACCOUNT, [original])

        assert result.errors == []
        assert result.transactions.account[0].date == late_evening

    @pytest.mark.asyncio
    async def test_custom_datetime_format_uses_local_wall_time_of_aware_dates(self):
        bank = _entity("Bank")
        aware = datetime(2025, 2, 3, 23, 30, tzinfo=tzoffset(None, 5 * 3600))
        naive_utc = datetime(2025, 2, 4, 8, 15)
        txs = [
            AccountTx(
                id=uuid4(),
                ref=ref,
                name=ref,
                amount=Dezimal("1"),
                currency="EUR",
                type=TxType.OUTFLOW,
                date=value,
                entity=bank,
                source=DataSource.REAL,
                product_type=ProductType.ACCOUNT,
                fees=Dezimal(0),
                retentions=Dezimal(0),
            )
            for ref, value in (("aware", aware), ("naive", naive_utc))
        ]

        rows = await TemplatedDataGenerator().process(
            txs,
            TemplatedDataProcessorParams(
                template=None,
                number_format=NumberFormat.ENGLISH,
                feature=Feature.TRANSACTIONS,
                products=[ProductType.ACCOUNT],
                datetime_format="%Y-%m-%d %H:%M",
                date_format=None,
            ),
        )

        date_index = rows[0].index("date")
        assert rows[1][date_index] == aware.astimezone(tzlocal()).strftime(
            "%Y-%m-%d %H:%M"
        )
        assert rows[2][date_index] == naive_utc.replace(tzinfo=timezone.utc).astimezone(
            tzlocal()
        ).strftime("%Y-%m-%d %H:%M")


BANK_ACCOUNT_FIELDS = [
    TemplatedField(field="date", name="fecha operacion"),
    TemplatedField(field="name", name="Concepto"),
    TemplatedField(field="amount", name="Importe"),
    TemplatedField(field="currency", name="Divisa", default_value="EUR"),
]


def _bank_candidate(
    product,
    table,
    fields=None,
    *,
    number_format=NumberFormat.ENGLISH,
    date_format=None,
    datetime_format=None,
):
    template = Template(
        id=None,
        name="",
        feature=Feature.TRANSACTIONS,
        type=TemplateType.IMPORT,
        fields=fields or BANK_ACCOUNT_FIELDS,
        products=[product],
    )
    params = TemplatedDataParserParams(
        template=template,
        number_format=number_format,
        feature=Feature.TRANSACTIONS,
        product=product,
        datetime_format=datetime_format,
        date_format=date_format,
        params={"entity": "Bank"},
    )
    return ImportCandidate(
        name="movements.xls",
        source=DataSource.MANUAL,
        params=params,
        data=table,
    )


async def _parse_bank(product, table, fields=None, **kwargs):
    return await TemplateDataParser().transactions(
        [_bank_candidate(product, table, fields, **kwargs)], {}
    )


def _local(*args):
    return datetime(*args, tzinfo=tzlocal())


class TestBankFileImport:
    @pytest.mark.asyncio
    async def test_imports_file_with_preamble_and_detected_formats(self):
        table = [
            ["Movimientos de la cuenta"],
            ["Cuenta", "ES91 2100 0418 4502 0005 1332"],
            [],
            ["", "Fecha Operación", "Concepto", "Importe", "Saldo"],
            ["", "31/01/2025", "Nómina   enero", "1.500,00", "2.500,00"],
            ["", "", " ", "", ""],
            ["", "05/02/2025", "Supermercado", "-45,30", "2.454,70"],
        ]

        result = await _parse_bank(ProductType.ACCOUNT, table)

        assert [error.type for error in result.errors] == [
            ImportErrorType.UNEXPECTED_COLUMN
        ]
        assert result.errors[0].detail == ["Saldo"]
        salary, groceries = result.transactions.account
        assert salary.name == "Nómina enero"
        assert salary.amount == Dezimal(1500)
        assert salary.type == TxType.INFLOW
        assert salary.currency == "EUR"
        assert salary.date == _local(2025, 1, 31)
        assert groceries.amount == Dezimal("45.30")
        assert groceries.type == TxType.OUTFLOW
        assert groceries.date == _local(2025, 2, 5)
        assert salary.ref and groceries.ref and salary.ref != groceries.ref

    @pytest.mark.asyncio
    async def test_imports_typed_spreadsheet_cells(self):
        table = [
            ["Fecha operación", "Concepto", "Importe"],
            [datetime(2025, 1, 2), "Nómina", Dezimal("1500.5")],
            [datetime(2025, 1, 5, 10, 30), "Supermercado", Dezimal("-45.3")],
        ]

        result = await _parse_bank(
            ProductType.ACCOUNT, table, number_format=NumberFormat.EUROPEAN
        )

        assert result.errors == []
        salary, groceries = result.transactions.account
        assert salary.amount == Dezimal("1500.5")
        assert salary.date == _local(2025, 1, 2)
        assert groceries.amount == Dezimal("45.3")
        assert groceries.date == _local(2025, 1, 5, 10, 30)

    @pytest.mark.asyncio
    async def test_falls_back_to_selected_number_format_when_ambiguous(self):
        table = [
            ["Fecha operación", "Concepto", "Importe"],
            ["2025-01-02", "Transfer", "1.250"],
        ]

        english = await _parse_bank(ProductType.ACCOUNT, table)
        european = await _parse_bank(
            ProductType.ACCOUNT, table, number_format=NumberFormat.EUROPEAN
        )

        assert english.transactions.account[0].amount == Dezimal("1.25")
        assert european.transactions.account[0].amount == Dezimal(1250)

    @pytest.mark.asyncio
    async def test_explicit_date_format_disables_detection(self):
        table = [
            ["Fecha operación", "Concepto", "Importe"],
            ["01/02/2025", "Transfer", "10"],
        ]

        detected = await _parse_bank(ProductType.ACCOUNT, table)
        explicit = await _parse_bank(ProductType.ACCOUNT, table, date_format="%m/%d/%Y")

        assert detected.transactions.account[0].date == _local(2025, 2, 1)
        assert explicit.transactions.account[0].date == _local(2025, 1, 2)

    @pytest.mark.asyncio
    async def test_generated_refs_are_stable_and_unique_for_repeated_rows(self):
        table = [
            ["Fecha operación", "Concepto", "Importe"],
            ["02/01/2025", "Coffee", "-2,50"],
            ["02/01/2025", "Coffee", "-2,50"],
        ]

        first = await _parse_bank(ProductType.ACCOUNT, table)
        second = await _parse_bank(ProductType.ACCOUNT, table)

        first_refs = [tx.ref for tx in first.transactions.account]
        assert len(set(first_refs)) == 2
        assert first_refs == [tx.ref for tx in second.transactions.account]

    @pytest.mark.asyncio
    async def test_keeps_file_reference_when_mapped(self):
        fields = BANK_ACCOUNT_FIELDS + [TemplatedField(field="ref", name="Nº mov")]
        table = [
            ["Fecha operación", "Concepto", "Importe", "Nº mov"],
            ["02/01/2025", "Coffee", "-2,50", "123"],
        ]

        result = await _parse_bank(ProductType.ACCOUNT, table, fields)

        assert result.transactions.account[0].ref == "123"

    @pytest.mark.asyncio
    async def test_derives_price_and_falls_back_to_isin_name(self):
        fields = [
            TemplatedField(field="date", name="Fecha"),
            TemplatedField(field="isin", name="ISIN"),
            TemplatedField(field="amount", name="Importe"),
            TemplatedField(field="shares", name="Participaciones"),
            TemplatedField(field="currency", name="currency", default_value="EUR"),
            TemplatedField(field="type", name="type", default_value="BUY"),
        ]
        table = [
            ["Fecha", "ISIN", "Importe", "Participaciones"],
            ["02/01/2025", "IE00B4L5Y983", "300,00", "2,5"],
            ["03/01/2025", "IE00B4L5Y983", "100,00", "0"],
        ]

        result = await _parse_bank(ProductType.FUND, table, fields)

        tx = result.transactions.investment[0]
        assert len(result.transactions.investment) == 1
        assert tx.name == "IE00B4L5Y983"
        assert tx.type == TxType.BUY
        assert tx.amount == Dezimal(300)
        assert tx.shares == Dezimal("2.5")
        assert tx.price == Dezimal(120)
        assert [(error.type, error.detail) for error in result.errors] == [
            (ImportErrorType.MISSING_FIELD, ["price"])
        ]


def _import_template(fields, products=(ProductType.ACCOUNT,)):
    return Template(
        id=uuid4(),
        name="Bank",
        feature=Feature.TRANSACTIONS,
        type=TemplateType.IMPORT,
        fields=fields,
        products=list(products),
    )


def _suggestable_fields(product):
    return [
        field
        for field in TEMPLATE_FIELD_MATRIX[Feature.TRANSACTIONS][product]
        if field.template_type != TemplateType.EXPORT
    ]


class TestSuggestFields:
    @pytest.mark.asyncio
    async def test_orders_matching_templates_and_skips_incompatible(self):
        table = [
            ["Movimientos de la cuenta"],
            [],
            ["Fecha Operación", "Concepto", "Importe", "Nº mov", "Saldo"],
            ["02/01/2025", "Nómina", "1.500,00", "1", "2.500,00"],
        ]
        basic = _import_template(BANK_ACCOUNT_FIELDS)
        with_ref = _import_template(
            BANK_ACCOUNT_FIELDS + [TemplatedField(field="ref", name="Nº mov")]
        )
        with_missing_optional = _import_template(
            BANK_ACCOUNT_FIELDS + [TemplatedField(field="fees", name="Comisión")]
        )
        missing_required = _import_template(
            [
                TemplatedField(field="date", name="Fecha valor"),
                TemplatedField(field="name", name="Concepto"),
                TemplatedField(field="amount", name="Importe"),
            ]
        )
        unrelated = _import_template(
            [
                TemplatedField(field="date", name="date"),
                TemplatedField(field="currency", name="currency", default_value="EUR"),
            ]
        )

        result = await TemplateDataParser().suggest_fields(
            table,
            _suggestable_fields(ProductType.ACCOUNT),
            [with_missing_optional, missing_required, basic, unrelated, with_ref],
        )

        assert result.matching_templates == [
            with_ref.id,
            basic.id,
            with_missing_optional.id,
        ]
        assert result.number_format == NumberFormat.EUROPEAN
        assert result.date_format == "%d/%m/%Y"

    @pytest.mark.asyncio
    async def test_returns_no_matches_without_templates(self):
        table = [
            ["Date", "Description", "Amount"],
            ["2025-01-02", "Salary", "1500.00"],
        ]

        result = await TemplateDataParser().suggest_fields(
            table, _suggestable_fields(ProductType.ACCOUNT), []
        )

        assert result.matching_templates == []
        assert result.number_format == NumberFormat.ENGLISH
        assert result.date_format == "ISO"

    @pytest.mark.asyncio
    async def test_imports_split_inflow_and_outflow_columns_and_textual_dates(self):
        template = Template(
            id=uuid4(),
            name="Split",
            feature=Feature.TRANSACTIONS,
            type=TemplateType.IMPORT,
            fields=[
                TemplatedField(field="date", name="FECHA"),
                TemplatedField(field="name", name="DESCRIPCIÓN"),
                TemplatedField(field="amount_in", name="ENTRADA DE DINERO"),
                TemplatedField(field="amount_out", name="SALIDA DE DINERO"),
                TemplatedField(field="currency", name="currency", default_value="EUR"),
            ],
            products=[ProductType.ACCOUNT],
        )
        table = [
            ["FECHA", "DESCRIPCIÓN", "ENTRADA DE DINERO", "SALIDA DE DINERO"],
            ["15 ene 2025", "Nómina", "1.500,00 €", ""],
            ["18 ene 2025", "Supermercado", "", "45,30 €"],
            ["20 ene 2025", "Fila vacía", "", ""],
        ]
        candidate = ImportCandidate(
            name="statement.pdf",
            source=DataSource.MANUAL,
            params=TemplatedDataParserParams(
                template=template,
                number_format=NumberFormat.EUROPEAN,
                feature=Feature.TRANSACTIONS,
                product=ProductType.ACCOUNT,
                datetime_format=None,
                date_format=None,
                params={"entity": "Trade Bank"},
            ),
            data=table,
        )

        parser = TemplateDataParser()
        suggestion = await parser.suggest_fields(
            table, _suggestable_fields(ProductType.ACCOUNT), [template]
        )
        assert suggestion.matching_templates == [template.id]

        result = await parser.transactions([candidate], {})
        assert len(result.transactions.account) == 2
        inflow, outflow = result.transactions.account
        assert inflow.type == TxType.INFLOW
        assert inflow.amount == Dezimal("1500.00")
        assert inflow.date == datetime(2025, 1, 15, tzinfo=tzlocal())
        assert outflow.type == TxType.OUTFLOW
        assert outflow.amount == Dezimal("45.30")
        assert len(result.errors) == 1
        assert result.errors[0].type == ImportErrorType.MISSING_FIELD
        assert _error_fields(result.errors[0]) == ["amount"]
