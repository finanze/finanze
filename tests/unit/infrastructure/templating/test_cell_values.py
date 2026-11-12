from datetime import date, datetime

import pytest

from domain.dezimal import Dezimal
from domain.export import NumberFormat
from infrastructure.templating.cell_values import (
    ISO_DATE_PATTERN,
    cell_text,
    detect_date_pattern,
    display_row,
    extract_number_currency,
    infer_number_format,
    is_empty_cell,
    parse_number,
    parse_with_date_pattern,
)


class TestParseNumber:
    @pytest.mark.parametrize(
        "value,number_format,expected",
        [
            ("1.234,56", NumberFormat.EUROPEAN, "1234.56"),
            ("1,234.56", NumberFormat.ENGLISH, "1234.56"),
            ("-1.234,56 €", NumberFormat.EUROPEAN, "-1234.56"),
            ("€ 12,50", NumberFormat.EUROPEAN, "12.50"),
            ("(12.50)", NumberFormat.ENGLISH, "-12.50"),
            ("12,50-", NumberFormat.EUROPEAN, "-12.50"),
            ("EUR 1,000.00", NumberFormat.ENGLISH, "1000.00"),
            ("1.000,00EUR", NumberFormat.EUROPEAN, "1000.00"),
            ("+5", NumberFormat.ENGLISH, "5"),
            ("1'234.5", NumberFormat.ENGLISH, "1234.5"),
            ("1 234,5", NumberFormat.EUROPEAN, "1234.5"),
            ("1.5E+3", NumberFormat.ENGLISH, "1500"),
        ],
    )
    def test_parses_text_numbers(self, value, number_format, expected):
        assert parse_number(value, number_format) == Dezimal(expected)

    def test_keeps_typed_numbers(self):
        assert parse_number(Dezimal("1.5"), NumberFormat.EUROPEAN) == Dezimal("1.5")
        assert parse_number(3, NumberFormat.EUROPEAN) == Dezimal(3)

    @pytest.mark.parametrize("value", ["abc", "1-2", "", True])
    def test_rejects_invalid_numbers(self, value):
        with pytest.raises(ValueError):
            parse_number(value, NumberFormat.ENGLISH)


class TestInferNumberFormat:
    @pytest.mark.parametrize(
        "values,expected",
        [
            (["1.234,56", "-12,50"], NumberFormat.EUROPEAN),
            (["1,234.56", "12.50"], NumberFormat.ENGLISH),
            (["1.234", "0,50"], NumberFormat.EUROPEAN),
            (["1.234.567"], NumberFormat.EUROPEAN),
            (["1.234"], None),
            (["1,5", "1.5"], None),
            (["12", "7"], None),
            ([Dezimal("1.5"), None], None),
        ],
    )
    def test_infers_column_format(self, values, expected):
        assert infer_number_format(values) == expected


class TestDetectDatePattern:
    @pytest.mark.parametrize(
        "values,expected",
        [
            (["2025-01-31", "2025-02-01T10:00:00"], ISO_DATE_PATTERN),
            (["31/01/2025", "01/02/2025"], "%d/%m/%Y"),
            (["01/31/2025", "02/01/2025"], "%m/%d/%Y"),
            (["01/02/2025"], "%d/%m/%Y"),
            (["31.01.25", "01.02.25"], "%d.%m.%y"),
            (["31-01-2025 10:30", "01-02-2025 08:00:15"], "%d-%m-%Y"),
            (["2025/01/31"], "%Y/%m/%d"),
        ],
    )
    def test_detects_pattern(self, values, expected):
        assert detect_date_pattern(values) == expected

    def test_ignores_blank_and_typed_values(self):
        assert detect_date_pattern(["", None, datetime(2025, 1, 1)]) is None

    def test_parses_dates_with_optional_time(self):
        assert parse_with_date_pattern("31/01/2025", "%d/%m/%Y") == datetime(
            2025, 1, 31
        )
        assert parse_with_date_pattern("31/01/2025  10:30", "%d/%m/%Y") == datetime(
            2025, 1, 31, 10, 30
        )

    @pytest.mark.parametrize(
        "raw,expected_pattern,expected_dt",
        [
            ("15 ene 2025", "%d/%m/%Y", datetime(2025, 1, 15)),
            ("03 de diciembre de 2025", "%d/%m/%Y", datetime(2025, 12, 3)),
            ("15 févr. 2025", "%d/%m/%Y", datetime(2025, 2, 15)),
            ("Jan 15, 2025", "%m/%d/%Y", datetime(2025, 1, 15)),
        ],
    )
    def test_detects_and_parses_textual_month_dates(
        self, raw, expected_pattern, expected_dt
    ):
        pattern = detect_date_pattern([raw])
        assert pattern == expected_pattern
        assert parse_with_date_pattern(raw, pattern) == expected_dt

    def test_extracts_unambiguous_currency_from_numbers(self):
        assert extract_number_currency("-99,99 EUR") == "EUR"
        assert extract_number_currency("99,99 €") == "EUR"
        assert extract_number_currency("USD 1,250.00") == "USD"
        assert extract_number_currency("£45.00") == "GBP"
        assert extract_number_currency("$45.00") is None
        assert extract_number_currency("15 ene") is None

    def test_rejects_values_not_matching_pattern(self):
        with pytest.raises(ValueError):
            parse_with_date_pattern("2025-01-31", "%d/%m/%Y")


class TestCellText:
    def test_renders_typed_values(self):
        assert display_row(
            [
                None,
                "Nómina",
                Dezimal("12.5"),
                datetime(2025, 1, 2),
                datetime(2025, 1, 2, 10, 30),
                date(2025, 1, 3),
            ]
        ) == [
            "",
            "Nómina",
            "12.5",
            "2025-01-02",
            "2025-01-02 10:30:00",
            "2025-01-03",
        ]

    def test_detects_empty_cells(self):
        assert is_empty_cell(None)
        assert is_empty_cell("  ")
        assert not is_empty_cell(Dezimal(0))
        assert not is_empty_cell(False)
        assert cell_text(False) == "False"
