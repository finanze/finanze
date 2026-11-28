from domain.template_fields import TemplateFieldType
from infrastructure.ai_import.extracted_rows import (
    apply_balance_directions,
    canonical_dates,
    canonical_numbers,
    drop_shared_refs,
    normalize_response,
)


class TestCanonicalNumbers:
    def test_each_value_uses_its_own_separator(self):
        assert canonical_numbers(["16,79", "10.76", "-1.666,34", "1,234.5", ""]) == [
            "16.79",
            "10.76",
            "-1666.34",
            "1234.5",
            "",
        ]

    def test_ambiguous_values_follow_the_response_majority(self):
        assert canonical_numbers(["16,79", "3.000", "5,10"]) == [
            "16.79",
            "3000",
            "5.10",
        ]
        assert canonical_numbers(["10.76", "3.000"]) == ["10.76", "3.000"]

    def test_unparseable_values_are_kept(self):
        assert canonical_numbers(["n/a", "12"]) == ["n/a", "12"]


class TestCanonicalDates:
    def test_day_first_dates_become_iso(self):
        assert canonical_dates(
            ["16/01/2025", "03/01/2025", "2025-01-20", "2025-13-01", ""]
        ) == ["2025-01-16", "2025-01-03", "2025-01-20", "2025-13-01", ""]

    def test_month_first_dates_are_detected(self):
        assert canonical_dates(["01/16/2025", "01/03/2025"]) == [
            "2025-01-16",
            "2025-01-03",
        ]

    def test_times_are_kept(self):
        assert canonical_dates(["16/01/2025 10:30"]) == ["2025-01-16T10:30:00"]


class TestNormalizeResponse:
    def test_rows_are_typed_and_cleaned(self):
        types = {
            "name": TemplateFieldType.TEXT,
            "amount": TemplateFieldType.DECIMAL,
            "date": TemplateFieldType.DATE,
            "iban": TemplateFieldType.TEXT,
            "balance": TemplateFieldType.DECIMAL,
        }
        rows = normalize_response(
            [
                {"name": " Coffee ", "amount": 3.5, "date": "16/01/2025", "iban": "C"},
                {"balance": "1.000,00"},
                {
                    "name": "Rent",
                    "amount": "-1.200,00",
                    "iban": "de89 3704 0044 0532 0130 00",
                },
            ],
            types,
        )
        assert rows == [
            {
                "name": "Coffee",
                "amount": "3.5",
                "date": "2025-01-16",
                "iban": "",
                "balance": "",
            },
            {
                "name": "Rent",
                "amount": "-1200.00",
                "date": "",
                "iban": "DE89370400440532013000",
                "balance": "",
            },
        ]


def _rows(*pairs):
    return [
        {"amount": amount, "balance": balance, "type": tx_type}
        for amount, balance, tx_type in pairs
    ]


class TestBalanceDirections:
    def test_chronological_balances(self):
        rows = _rows(
            ("100", "1100", ""),
            ("40", "1060", "INFLOW"),
            ("-10", "1070", "OUTFLOW"),
            ("5", "", "OUTFLOW"),
        )
        apply_balance_directions(rows)
        assert [(row["amount"], row["type"]) for row in rows] == [
            ("100", ""),
            ("-40", ""),
            ("10", ""),
            ("5", "OUTFLOW"),
        ]

    def test_newest_first_balances(self):
        rows = _rows(
            ("10", "1070", "OUTFLOW"),
            ("40", "1060", "INTEREST"),
            ("100", "1100", ""),
        )
        apply_balance_directions(rows)
        assert [(row["amount"], row["type"]) for row in rows] == [
            ("10", ""),
            ("-40", "INTEREST"),
            ("100", ""),
        ]

    def test_ambiguous_orientation_changes_nothing(self):
        rows = _rows(("10", "100", ""), ("10", "110", ""))
        apply_balance_directions(rows)
        assert [row["amount"] for row in rows] == ["10", "10"]


class TestSharedRefs:
    def test_refs_repeated_on_different_rows_are_dropped(self):
        rows = [
            {"ref": "C", "date": "2025-01-01", "amount": "1", "name": "A"},
            {"ref": "C", "date": "2025-01-02", "amount": "2", "name": "B"},
            {"ref": "R-1", "date": "2025-01-03", "amount": "3", "name": "C"},
            {"ref": "R-1", "date": "2025-01-03", "amount": "3", "name": "C"},
        ]
        drop_shared_refs(rows)
        assert [row["ref"] for row in rows] == ["", "", "R-1", "R-1"]
