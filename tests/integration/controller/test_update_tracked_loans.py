import pytest
from datetime import date
from uuid import uuid4

from domain.dezimal import Dezimal
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import (
    InstallmentFrequency,
    InterestType,
    Loan,
    LoanType,
    ManualEntryData,
    ManualPositionData,
    ProductType,
)

URL = "/api/v1/data/manual/positions/update-loans"
SIGNUP_URL = "/api/v1/signup"
USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _make_mpd(entry_id=None, tracking_ref_outstanding=None, tracking_ref_date=None):
    return ManualPositionData(
        entry_id=entry_id or uuid4(),
        global_position_id=uuid4(),
        product_type=ProductType.LOAN,
        data=ManualEntryData(
            track=True,
            tracking_ref_outstanding=tracking_ref_outstanding,
            tracking_ref_date=tracking_ref_date,
        ),
    )


def _make_loan(
    entry_id=None,
    interest_type=InterestType.FIXED,
    interest_rate=Dezimal("0.03"),
    loan_amount=Dezimal(100000),
    principal_outstanding=Dezimal(80000),
    creation=date(2020, 1, 15),
    maturity=date(2050, 1, 15),
    euribor_rate=None,
    fixed_years=None,
    fixed_interest_rate=None,
    installment_frequency=InstallmentFrequency.MONTHLY,
):
    return Loan(
        id=entry_id or uuid4(),
        type=LoanType.MORTGAGE,
        currency="EUR",
        current_installment=Dezimal(500),
        interest_rate=interest_rate,
        loan_amount=loan_amount,
        creation=creation,
        maturity=maturity,
        principal_outstanding=principal_outstanding,
        interest_type=interest_type,
        installment_frequency=installment_frequency,
        euribor_rate=euribor_rate,
        fixed_years=fixed_years,
        fixed_interest_rate=fixed_interest_rate,
    )


class TestUpdateTrackedLoans:
    @pytest.mark.asyncio
    async def test_fixed_loan_first_run_initializes_ref(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(entry_id=entry_id)

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        response = await client.post(URL)
        assert response.status_code == 204

        manual_position_data_port.update_tracking_ref.assert_awaited_once()
        ref_args = manual_position_data_port.update_tracking_ref.await_args
        assert ref_args[0][0] == entry_id
        assert ref_args[0][1] == loan.principal_outstanding
        assert ref_args[0][2] is not None

    @pytest.mark.asyncio
    async def test_fixed_loan_with_ref_decreases_outstanding(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        entry_id = uuid4()
        ref_date = date(2025, 4, 15)
        ref_outstanding = Dezimal(80000)
        mpd = _make_mpd(
            entry_id=entry_id,
            tracking_ref_outstanding=ref_outstanding,
            tracking_ref_date=ref_date,
        )
        loan = _make_loan(
            entry_id=entry_id,
            principal_outstanding=ref_outstanding,
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        response = await client.post(URL)
        assert response.status_code == 204

        position_port.update_loan_position.assert_awaited_once()
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["principal_outstanding"] < ref_outstanding
        manual_position_data_port.update_tracking_ref.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_variable_loan_includes_euribor(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            entry_id=entry_id,
            interest_type=InterestType.VARIABLE,
            interest_rate=Dezimal("0.01"),
            euribor_rate=Dezimal("0.035"),
            principal_outstanding=Dezimal(80000),
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        response = await client.post(URL)
        assert response.status_code == 204

        position_port.update_loan_position.assert_awaited_once()
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["current_installment"].val > 0

    @pytest.mark.asyncio
    async def test_mixed_loan_during_fixed_period(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            entry_id=entry_id,
            interest_type=InterestType.MIXED,
            interest_rate=Dezimal("0.01"),
            euribor_rate=Dezimal("0.03"),
            fixed_years=50,
            fixed_interest_rate=Dezimal("0.02"),
            principal_outstanding=Dezimal(80000),
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        response = await client.post(URL)
        assert response.status_code == 204

        position_port.update_loan_position.assert_awaited_once()
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["current_installment"].val > 0
        assert call_kwargs["principal_outstanding"].val > 0

    @pytest.mark.asyncio
    async def test_matured_loan_not_updated(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan = _make_loan(
            entry_id=entry_id,
            maturity=date.today(),
            principal_outstanding=Dezimal(80000),
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan

        response = await client.post(URL)
        assert response.status_code == 204

        position_port.update_loan_position.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_loans_mixed_results(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        id1 = uuid4()
        mpd1 = _make_mpd(entry_id=id1)
        loan1 = _make_loan(entry_id=id1)

        id2 = uuid4()
        mpd2 = _make_mpd(entry_id=id2)
        loan2 = _make_loan(entry_id=id2, maturity=date.today())

        id3 = uuid4()
        mpd3 = _make_mpd(entry_id=id3)

        manual_position_data_port.get_trackable_loans.return_value = [mpd1, mpd2, mpd3]

        async def get_loan(entry_id):
            if entry_id == id1:
                return loan1
            if entry_id == id2:
                return loan2
            return None

        position_port.get_loan_by_entry_id.side_effect = get_loan

        response = await client.post(URL)
        assert response.status_code == 204

        assert position_port.update_loan_position.await_count == 1
        call_kwargs = position_port.update_loan_position.await_args.kwargs
        assert call_kwargs["entry_id"] == id1

    @pytest.mark.asyncio
    async def test_lock_conflict_returns_409(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        manual_position_data_port.get_trackable_loans.side_effect = ExecutionConflict(
            "Already running"
        )

        response = await client.post(URL)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_quarterly_frequency_produces_different_payment(
        self, client, position_port, manual_position_data_port
    ):
        await _signup(client)
        entry_id = uuid4()
        mpd = _make_mpd(entry_id=entry_id)
        loan_monthly = _make_loan(
            entry_id=entry_id,
            installment_frequency=InstallmentFrequency.MONTHLY,
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan_monthly

        response = await client.post(URL)
        assert response.status_code == 204

        position_port.update_loan_position.assert_awaited_once()
        kwargs_m = position_port.update_loan_position.await_args.kwargs
        monthly_installment = kwargs_m["current_installment"]

        position_port.reset_mock()
        manual_position_data_port.reset_mock()

        loan_quarterly = _make_loan(
            entry_id=entry_id,
            installment_frequency=InstallmentFrequency.QUARTERLY,
        )
        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_loan_by_entry_id.return_value = loan_quarterly

        response = await client.post(URL)
        assert response.status_code == 204

        position_port.update_loan_position.assert_awaited_once()
        kwargs_q = position_port.update_loan_position.await_args.kwargs
        quarterly_installment = kwargs_q["current_installment"]

        assert monthly_installment != quarterly_installment
