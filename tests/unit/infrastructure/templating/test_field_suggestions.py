from datetime import datetime

from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.export import NumberFormat
from domain.global_position import ProductType
from domain.template_fields import TEMPLATE_FIELD_MATRIX
from domain.template_type import TemplateType
from infrastructure.templating.field_suggestions import suggest_template_fields


def _fields(product):
    return [
        field
        for field in TEMPLATE_FIELD_MATRIX[Feature.TRANSACTIONS][product]
        if field.template_type != TemplateType.EXPORT
    ]


def _mapping(result):
    return [(field.field, field.name) for field in result.fields]


class TestSuggestTemplateFields:
    def test_finds_header_after_preamble_and_ignores_unknown_columns(self):
        table = [
            ["Movimientos de la cuenta", "", "", "", ""],
            ["Cuenta", "ES91 2100 0418 4502 0005 1332", "", "", ""],
            [],
            ["Fecha operación", "Fecha valor", "Concepto", "Importe", "Saldo"],
            ["02/01/2025", "02/01/2025", "Nómina", "1.500,00", "2.500,00"],
            ["05/01/2025", "06/01/2025", "Supermercado", "-45,30", "2.454,70"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert result.headers == [
            "Fecha operación",
            "Fecha valor",
            "Concepto",
            "Importe",
            "Saldo",
        ]
        assert _mapping(result) == [
            ("date", "Fecha operación"),
            ("name", "Concepto"),
            ("amount", "Importe"),
        ]

    def test_maps_english_headers(self):
        table = [
            ["Date", "Description", "Amount", "Currency", "Reference"],
            ["2025-01-02", "Salary", "1500.00", "EUR", "R1"],
            ["2025-01-05", "Groceries", "-45.30", "EUR", "R2"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert _mapping(result) == [
            ("date", "Date"),
            ("name", "Description"),
            ("amount", "Amount"),
            ("currency", "Currency"),
            ("ref", "Reference"),
        ]

    def test_accepts_typed_spreadsheet_cells(self):
        table = [
            ["Fecha operación", "Concepto", "Importe", "Divisa"],
            [datetime(2025, 1, 2), "Nómina", Dezimal(1500), "EUR"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert _mapping(result) == [
            ("date", "Fecha operación"),
            ("name", "Concepto"),
            ("amount", "Importe"),
            ("currency", "Divisa"),
        ]

    def test_skips_columns_whose_content_does_not_match(self):
        table = [
            ["Fecha", "Concepto", "Importe"],
            ["02/01/2025", "Nómina", "n/a"],
            ["05/01/2025", "Supermercado", "pending"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert _mapping(result) == [("date", "Fecha"), ("name", "Concepto")]

    def test_uses_headers_only_when_there_are_no_data_rows(self):
        table = [["Fecha", "Concepto", "Importe"]]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert _mapping(result) == [
            ("date", "Fecha"),
            ("name", "Concepto"),
            ("amount", "Importe"),
        ]

    def test_maps_investment_columns_once_each(self):
        table = [
            ["Fecha orden", "Fecha", "ISIN", "Participaciones", "Importe"],
            ["01/01/2025", "02/01/2025", "IE00B4L5Y983", "2,5", "300,00"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.FUND))

        assert _mapping(result) == [
            ("order_date", "Fecha orden"),
            ("date", "Fecha"),
            ("isin", "ISIN"),
            ("shares", "Participaciones"),
            ("amount", "Importe"),
        ]

    def test_rejects_isin_column_with_invalid_codes(self):
        table = [
            ["Fecha", "ISIN", "Importe"],
            ["02/01/2025", "not an isin", "300,00"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.STOCK_ETF))

        assert "isin" not in [field.field for field in result.fields]

    def test_returns_empty_suggestion_for_empty_table(self):
        result = suggest_template_fields([[], ["", " "]], _fields(ProductType.ACCOUNT))

        assert result.headers == []
        assert result.fields == []
        assert result.number_format is None
        assert result.date_format is None


class TestSuggestedFormats:
    def test_detects_european_numbers_and_day_first_dates(self):
        table = [
            ["Fecha", "Concepto", "Importe"],
            ["02/01/2025", "Nómina", "1.500,00"],
            ["25/01/2025", "Supermercado", "-45,30"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert result.number_format == NumberFormat.EUROPEAN
        assert result.date_format == "%d/%m/%Y"

    def test_detects_english_numbers_and_iso_dates(self):
        table = [
            ["Date", "Description", "Amount"],
            ["2025-01-02", "Salary", "1,500.00"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert result.number_format == NumberFormat.ENGLISH
        assert result.date_format == "ISO"

    def test_ignores_unmapped_columns_and_ambiguous_numbers(self):
        table = [
            ["Fecha", "Concepto", "Importe", "Saldo"],
            ["02.01.2025", "Transfer", "1.500", "2.500,75"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert result.number_format is None
        assert result.date_format == "%d.%m.%Y"

    def test_conflicting_number_columns_have_no_format(self):
        table = [
            ["Fecha", "ISIN", "Participaciones", "Importe"],
            ["02/01/2025", "IE00B4L5Y983", "2.5", "300,00"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.FUND))

        assert result.number_format is None

    def test_typed_cells_have_no_formats(self):
        table = [
            ["Fecha operación", "Concepto", "Importe"],
            [datetime(2025, 1, 2), "Nómina", Dezimal(1500)],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert result.number_format is None
        assert result.date_format is None

    def test_detects_currency_from_header_values_and_preamble(self):
        from_header = suggest_template_fields(
            [
                ["F. VALOR", "DESCRIPCIÓN", "IMPORTE (€)"],
                ["2025-01-02", "Nómina", "1500"],
            ],
            _fields(ProductType.ACCOUNT),
        )
        assert from_header.detected_currency == "EUR"
        assert from_header.missing_required_fields == ["currency"]

        from_values = suggest_template_fields(
            [
                ["Fecha", "Concepto", "Importe"],
                ["02/01/2025", "Nómina", "1.500,00 EUR"],
            ],
            _fields(ProductType.ACCOUNT),
        )
        assert from_values.detected_currency == "EUR"

        from_preamble = suggest_template_fields(
            [
                ["CUENTA CORRIENTE EUR: ES91 2100 0418 4502 0005 1332"],
                ["Fecha", "Concepto", "Importe"],
                ["02/01/2025", "Nómina", "1.500,00"],
            ],
            _fields(ProductType.ACCOUNT),
        )
        assert from_preamble.detected_currency == "EUR"

    def test_maps_split_inflow_and_outflow_including_empty_sibling_column(self):
        table = [
            ["FECHA", "DESCRIPCIÓN", "ENTRADA DE DINERO", "SALIDA DE DINERO"],
            ["15 ene 2025", "Supermercado", "", "45,30 €"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert _mapping(result) == [
            ("date", "FECHA"),
            ("name", "DESCRIPCIÓN"),
            ("amount_in", "ENTRADA DE DINERO"),
            ("amount_out", "SALIDA DE DINERO"),
        ]
        assert result.detected_currency == "EUR"
        assert result.missing_required_fields == ["currency"]

    def test_reports_missing_required_fields_when_amount_is_absent(self):
        table = [
            ["Fecha", "Concepto"],
            ["02/01/2025", "Nómina"],
        ]

        result = suggest_template_fields(table, _fields(ProductType.ACCOUNT))

        assert result.missing_required_fields == ["amount", "currency"]
