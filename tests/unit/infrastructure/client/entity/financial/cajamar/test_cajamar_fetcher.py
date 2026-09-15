from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.global_position import (
    InterestType,
    LoanType,
    ProductType,
)
from domain.native_entities import CAJAMAR
from infrastructure.client.entity.financial.cajamar.cajamar_fetcher import (
    CajamarFetcher,
)


def _fetcher():
    fetcher = CajamarFetcher()
    fetcher._client = MagicMock()
    fetcher._client.get_loan = AsyncMock(return_value={})
    fetcher._client.get_leasing = AsyncMock(return_value={})
    fetcher._client.get_confirming = AsyncMock(return_value={})
    fetcher._client.get_fidis_intro = AsyncMock(return_value={})
    fetcher._client.get_fidis_details = AsyncMock(return_value={})
    fetcher._client.get_position = AsyncMock(return_value={})
    return fetcher


def _standard_entry(**overrides):
    entry = {
        "id": "fin-1",
        "productId": "17875913980340395546",
        "account": "ES7600000000000000000001",
        "origin": "C",
        "type": "PR",
        "description": "PRESTAMO PERSONAL",
        "association": None,
        "currency": "EUR",
        "amountGranted": "10.000,00",
        "pendingAmount": "4.500,50",
    }
    entry.update(overrides)
    return entry


@pytest.mark.asyncio
async def test_standard_loan_uses_origin_and_skips_other_endpoints():
    fetcher = _fetcher()
    fetcher._client.get_loan = AsyncMock(
        return_value={
            "description": "PRESTAMO PERSONAL",
            "currency": "EUR",
            "amortizationQuotaAmount": "250,00",
            "amountGranted": "10000.00",
            "pendingAmount": "4500.50",
            "agreementDate": "2020-01-15",
            "maturiryDate": "2030-01-15",
            "nextAmortizationDate": "2026-08-01",
            "interest": "3,50",
            "amortizationType": "CUOTA CONSTANTE",
        }
    )

    loans, credits = await fetcher._build_financings(
        {"financings": [_standard_entry()]}
    )

    fetcher._client.get_loan.assert_awaited_once_with(
        "17875913980340395546", origin="C"
    )
    fetcher._client.get_fidis_intro.assert_not_awaited()
    fetcher._client.get_leasing.assert_not_awaited()
    fetcher._client.get_confirming.assert_not_awaited()
    assert credits == []
    assert len(loans) == 1
    loan = loans[0]
    assert loan.type == LoanType.STANDARD
    assert loan.interest_type == InterestType.FIXED
    assert loan.loan_amount == Dezimal("10000.00")
    assert loan.principal_outstanding == Dezimal("4500.50")
    assert loan.current_installment == Dezimal("250.00")
    assert loan.interest_rate == Dezimal("0.035")
    assert loan.creation == date(2020, 1, 15)
    assert loan.maturity == date(2030, 1, 15)
    assert loan.next_payment_date == date(2026, 8, 1)
    assert loan.name == "PRESTAMO PERSONAL"


@pytest.mark.asyncio
async def test_standard_loan_skipped_when_details_empty():
    fetcher = _fetcher()
    fetcher._client.get_loan = AsyncMock(return_value={})

    loans, credits = await fetcher._build_financings(
        {"financings": [_standard_entry()]}
    )

    assert credits == []
    assert loans == []


@pytest.mark.asyncio
async def test_standard_loan_skipped_when_details_fail():
    fetcher = _fetcher()
    fetcher._client.get_loan = AsyncMock(side_effect=RuntimeError("500"))

    loans, credits = await fetcher._build_financings(
        {"financings": [_standard_entry()]}
    )

    assert credits == []
    assert loans == []


@pytest.mark.asyncio
async def test_mortgage_from_description():
    fetcher = _fetcher()
    fetcher._client.get_loan = AsyncMock(
        return_value={
            "description": "HIPOTECA VIVIENDA",
            "currency": "EUR",
            "amortizationQuotaAmount": "800",
            "amountGranted": "150000",
            "pendingAmount": "90000",
            "agreementDate": "2018-03-01",
            "maturiryDate": "2048-03-01",
            "interest": "2.1",
        }
    )

    loans, _ = await fetcher._build_financings(
        {"financings": [_standard_entry(description="HIPOTECA VIVIENDA")]}
    )

    assert loans[0].type == LoanType.MORTGAGE
    assert loans[0].interest_type == InterestType.VARIABLE


@pytest.mark.asyncio
async def test_fidis_never_calls_loan_and_maps_credit():
    fetcher = _fetcher()
    fetcher._client.get_fidis_intro = AsyncMock(
        return_value={
            "optk": "token-1",
            "lineCredits": [
                {
                    "operation": "001122",
                    "product": "FIDIS",
                    "interest": "7,00",
                    "dateConfirm": "2024-02-10",
                    "creditLimit": "20000.00",
                    "availableImport": "5000.00",
                    "index": 0,
                }
            ],
        }
    )
    fetcher._client.get_fidis_details = AsyncMock(
        return_value={
            "description": "LINEA FIDIS",
            "creditLimitAvailable": "4500.00",
            "interest": "6,50",
            "dateConfirm": "2024-02-10",
        }
    )

    loans, credits = await fetcher._build_financings(
        {
            "financings": [
                _standard_entry(
                    type="CR",
                    account="001122",
                    productId="fidis-1",
                    description="CREDITO FIDIS",
                    amountGranted="20000.00",
                    pendingAmount="15500.00",
                )
            ]
        }
    )

    fetcher._client.get_loan.assert_not_awaited()
    fetcher._client.get_leasing.assert_not_awaited()
    fetcher._client.get_confirming.assert_not_awaited()
    fetcher._client.get_fidis_intro.assert_awaited_once()
    fetcher._client.get_fidis_details.assert_awaited_once_with(0, "token-1")
    assert loans == []
    assert len(credits) == 1
    credit = credits[0]
    assert credit.credit_limit == Dezimal("20000.00")
    assert credit.drawn_amount == Dezimal("15500.00")
    assert credit.interest_rate == Dezimal("0.065")
    assert credit.name == "LINEA FIDIS"
    assert credit.creation == date(2024, 2, 10)


@pytest.mark.asyncio
async def test_leasing_uses_leasing_endpoint():
    fetcher = _fetcher()
    fetcher._client.get_leasing = AsyncMock(
        return_value={
            "description": "LEASING VEHICULO",
            "fee": "320,15",
            "outstandingCapital": "12000.00",
            "hiringDate": "2022-05-01",
            "endDate": "2027-05-01",
            "nextAmortization": "2026-09-01",
            "interest": "4,25",
        }
    )

    loans, credits = await fetcher._build_financings(
        {
            "financings": [
                _standard_entry(
                    type="LS",
                    productId="lease-9",
                    association="A1",
                    description="LEASING",
                    amountGranted="18000.00",
                    pendingAmount="13000.00",
                )
            ]
        }
    )

    fetcher._client.get_leasing.assert_awaited_once_with("lease-9", association="A1")
    fetcher._client.get_loan.assert_not_awaited()
    fetcher._client.get_confirming.assert_not_awaited()
    assert credits == []
    assert len(loans) == 1
    assert loans[0].name == "LEASING VEHICULO"
    assert loans[0].current_installment == Dezimal("320.15")
    assert loans[0].principal_outstanding == Dezimal("12000.00")
    assert loans[0].creation == date(2022, 5, 1)
    assert loans[0].maturity == date(2027, 5, 1)


@pytest.mark.asyncio
async def test_confirming_uses_confirming_endpoint():
    fetcher = _fetcher()
    fetcher._client.get_confirming = AsyncMock(
        return_value={"title": "CONFIRMING ACME"}
    )

    loans, credits = await fetcher._build_financings(
        {
            "financings": [
                _standard_entry(
                    type="CF",
                    productId="conf-3",
                    description="CONFIRMING",
                    amountGranted="8000.00",
                    pendingAmount="2500.00",
                )
            ]
        }
    )

    fetcher._client.get_confirming.assert_awaited_once_with("conf-3")
    fetcher._client.get_loan.assert_not_awaited()
    fetcher._client.get_leasing.assert_not_awaited()
    assert credits == []
    assert len(loans) == 1
    assert loans[0].name == "CONFIRMING ACME"
    assert loans[0].loan_amount == Dezimal("8000.00")
    assert loans[0].principal_outstanding == Dezimal("2500.00")


@pytest.mark.asyncio
async def test_confirming_falls_back_when_details_fail():
    fetcher = _fetcher()
    fetcher._client.get_confirming = AsyncMock(side_effect=RuntimeError("500"))

    loans, _ = await fetcher._build_financings(
        {
            "financings": [
                _standard_entry(
                    type="CF",
                    productId="conf-3",
                    description="CONFIRMING",
                    amountGranted="8000.00",
                    pendingAmount="2500.00",
                )
            ]
        }
    )

    assert loans[0].name == "CONFIRMING"
    assert loans[0].loan_amount == Dezimal("8000.00")


@pytest.mark.asyncio
async def test_global_position_splits_loans_and_credits():
    fetcher = _fetcher()
    fetcher._client.get_position = AsyncMock(
        return_value={
            "accounts": [
                {
                    "id": "acc-1",
                    "iban": "ES76 0000 0000 0000 0000 0001",
                    "currency": "EUR",
                    "accountingBalance": "1000.00",
                    "availableBalance": "900.00",
                }
            ],
            "financings": [
                _standard_entry(),
                _standard_entry(
                    type="CR",
                    account="001122",
                    productId="fidis-1",
                    description="CREDITO FIDIS",
                    amountGranted="20000.00",
                    pendingAmount="5000.00",
                ),
            ],
        }
    )
    fetcher._client.get_loan = AsyncMock(
        return_value={
            "description": "PRESTAMO PERSONAL",
            "currency": "EUR",
            "amortizationQuotaAmount": "250",
            "amountGranted": "10000",
            "pendingAmount": "4500.50",
            "agreementDate": "2020-01-15",
            "maturiryDate": "2030-01-15",
            "interest": "3.5",
            "amortizationType": "CUOTA CONSTANTE",
        }
    )
    fetcher._client.get_fidis_intro = AsyncMock(
        return_value={
            "optk": "token-1",
            "lineCredits": [
                {
                    "operation": "001122",
                    "creditLimit": "20000.00",
                    "availableImport": "15000.00",
                    "interest": "7",
                    "index": 0,
                }
            ],
        }
    )
    fetcher._client.get_fidis_details = AsyncMock(return_value={})

    position = await fetcher.global_position()

    assert position.entity is CAJAMAR
    assert ProductType.ACCOUNT in position.products
    assert ProductType.LOAN in position.products
    assert ProductType.CREDIT in position.products
    assert ProductType.CREDIT in CAJAMAR.products
    assert len(position.products[ProductType.LOAN].entries) == 1
    assert len(position.products[ProductType.CREDIT].entries) == 1


def test_parse_money_european_and_us():
    assert CajamarFetcher._parse_money("10.000,50") == Dezimal("10000.50")
    assert CajamarFetcher._parse_money("10,000.50") == Dezimal("10000.50")
    assert CajamarFetcher._parse_money("1.234") == Dezimal("1.234")
    assert CajamarFetcher._parse_money("—") is None


def test_parse_interest_divides_by_100():
    assert CajamarFetcher._parse_interest("3,50") == Dezimal("0.035")
    assert CajamarFetcher._parse_interest(None) == Dezimal(0)
