from datetime import date

from domain.dezimal import Dezimal
from domain.fetch_record import DataSource
from domain.global_position import CreditDetail, Credits


class TestCreditDetail:
    def test_available_amount_is_derived(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("10000"),
            drawn_amount=Dezimal("6407"),
            interest_rate=Dezimal("0.0325"),
        )
        assert credit.available_amount == Dezimal("3593")

    def test_available_amount_when_fully_drawn(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("5000"),
            drawn_amount=Dezimal("5000"),
            interest_rate=Dezimal("0.03"),
        )
        assert credit.available_amount == Dezimal("0")

    def test_available_amount_when_nothing_drawn(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("10000"),
            drawn_amount=Dezimal("0"),
            interest_rate=Dezimal("0.03"),
        )
        assert credit.available_amount == Dezimal("10000")

    def test_pledged_credit(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("10000"),
            drawn_amount=Dezimal("6407"),
            interest_rate=Dezimal("0.0325"),
            pledged_amount=Dezimal("20000"),
        )
        assert credit.pledged_amount == Dezimal("20000")

    def test_non_pledged_credit(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("10000"),
            drawn_amount=Dezimal("6407"),
            interest_rate=Dezimal("0.0325"),
        )
        assert credit.pledged_amount is None

    def test_defaults(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("10000"),
            drawn_amount=Dezimal("0"),
            interest_rate=Dezimal("0.03"),
        )
        assert credit.name is None
        assert credit.pledged_amount is None
        assert credit.creation is None
        assert credit.source == DataSource.REAL

    def test_with_all_fields(self):
        credit = CreditDetail(
            id=None,
            currency="EUR",
            credit_limit=Dezimal("10000"),
            drawn_amount=Dezimal("6407"),
            interest_rate=Dezimal("0.0325"),
            name="Cuenta CREDITO 4895",
            pledged_amount=Dezimal("20000.01738"),
            creation=date(2026, 1, 11),
            source=DataSource.REAL,
        )
        assert credit.name == "Cuenta CREDITO 4895"
        assert credit.creation == date(2026, 1, 11)


class TestCredits:
    def test_entries_list(self):
        credits = Credits(
            entries=[
                CreditDetail(
                    id=None,
                    currency="EUR",
                    credit_limit=Dezimal("10000"),
                    drawn_amount=Dezimal("6407"),
                    interest_rate=Dezimal("0.0325"),
                ),
                CreditDetail(
                    id=None,
                    currency="EUR",
                    credit_limit=Dezimal("5000"),
                    drawn_amount=Dezimal("2000"),
                    interest_rate=Dezimal("0.04"),
                ),
            ]
        )
        assert len(credits.entries) == 2

    def test_empty_entries(self):
        credits = Credits(entries=[])
        assert len(credits.entries) == 0
