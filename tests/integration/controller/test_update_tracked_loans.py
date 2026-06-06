import pytest
from datetime import date
from uuid import uuid4

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import (
    GlobalPosition,
    InstallmentFrequency,
    InterestType,
    Loan,
    Loans,
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


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_mpd(
    entry_id=None,
    global_position_id=None,
    tracking_ref_outstanding=None,
    tracking_ref_date=None,
):
    return ManualPositionData(
        entry_id=entry_id or uuid4(),
        global_position_id=global_position_id or uuid4(),
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


def _make_position(global_position_id, loans, entity=None):
    return GlobalPosition(
        id=global_position_id,
        entity=entity or _make_entity(),
        products={ProductType.LOAN: Loans(entries=loans)},
    )


def _saved_loan(position_port):
    saved_position = position_port.save.await_args[0][0]
    return saved_position.products[ProductType.LOAN].entries[0]


class TestUpdateTrackedLoans:
    @pytest.mark.asyncio
    async def test_fixed_loan_creates_snapshot(
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(entry_id=entry_id)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200
        body = await response.get_json()
        assert body["hadTracked"] is True
        assert body["changed"] is True

        position_port.save.assert_awaited()

    @pytest.mark.asyncio
    async def test_fixed_loan_with_ref_decreases_outstanding(
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        entry_id = uuid4()
        gpid = uuid4()
        ref_date = date(2025, 4, 15)
        ref_outstanding = Dezimal(80000)
        loan = _make_loan(entry_id=entry_id, principal_outstanding=ref_outstanding)
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(
            entry_id=entry_id,
            global_position_id=gpid,
            tracking_ref_outstanding=ref_outstanding,
            tracking_ref_date=ref_date,
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200
        body = await response.get_json()
        assert body["changed"] is True

        saved_loan = _saved_loan(position_port)
        assert saved_loan.principal_outstanding < ref_outstanding

    @pytest.mark.asyncio
    async def test_variable_loan_includes_euribor(
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(
            entry_id=entry_id,
            interest_type=InterestType.VARIABLE,
            interest_rate=Dezimal("0.01"),
            euribor_rate=Dezimal("0.035"),
            principal_outstanding=Dezimal(80000),
        )
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200

        position_port.save.assert_awaited()
        saved_loan = _saved_loan(position_port)
        assert saved_loan.current_installment.val > 0

    @pytest.mark.asyncio
    async def test_mixed_loan_during_fixed_period(
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(
            entry_id=entry_id,
            interest_type=InterestType.MIXED,
            interest_rate=Dezimal("0.01"),
            euribor_rate=Dezimal("0.03"),
            fixed_years=50,
            fixed_interest_rate=Dezimal("0.02"),
            principal_outstanding=Dezimal(80000),
        )
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200

        position_port.save.assert_awaited()
        saved_loan = _saved_loan(position_port)
        assert saved_loan.current_installment.val > 0
        assert saved_loan.principal_outstanding.val > 0

    @pytest.mark.asyncio
    async def test_matured_loan_not_updated(
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        entry_id = uuid4()
        gpid = uuid4()
        loan = _make_loan(
            entry_id=entry_id,
            maturity=date.today(),
            principal_outstanding=Dezimal(80000),
        )
        position = _make_position(global_position_id=gpid, loans=[loan])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200
        body = await response.get_json()
        assert body["changed"] is False

        position_port.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_loans_mixed_results(
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        g1, g2, g3 = uuid4(), uuid4(), uuid4()
        mpd1 = _make_mpd(entry_id=id1, global_position_id=g1)
        mpd2 = _make_mpd(entry_id=id2, global_position_id=g2)
        mpd3 = _make_mpd(entry_id=id3, global_position_id=g3)

        pos1 = _make_position(global_position_id=g1, loans=[_make_loan(entry_id=id1)])
        pos2 = _make_position(
            global_position_id=g2,
            loans=[_make_loan(entry_id=id2, maturity=date.today())],
        )

        manual_position_data_port.get_trackable_loans.return_value = [mpd1, mpd2, mpd3]
        virtual_import_registry.get_last_import_records.return_value = []

        async def get_by_id(global_position_id):
            if global_position_id == g1:
                return pos1
            if global_position_id == g2:
                return pos2
            return None

        position_port.get_by_id.side_effect = get_by_id

        response = await client.post(URL)
        assert response.status_code == 200

        assert position_port.save.await_count == 1

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
        self, client, position_port, manual_position_data_port, virtual_import_registry
    ):
        await _signup(client)
        entry_id = uuid4()
        gpid = uuid4()
        loan_monthly = _make_loan(
            entry_id=entry_id,
            installment_frequency=InstallmentFrequency.MONTHLY,
        )
        position_m = _make_position(global_position_id=gpid, loans=[loan_monthly])
        mpd = _make_mpd(entry_id=entry_id, global_position_id=gpid)

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position_m
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200
        monthly_installment = _saved_loan(position_port).current_installment

        position_port.reset_mock()
        manual_position_data_port.reset_mock()
        virtual_import_registry.reset_mock()

        loan_quarterly = _make_loan(
            entry_id=entry_id,
            installment_frequency=InstallmentFrequency.QUARTERLY,
        )
        position_q = _make_position(global_position_id=gpid, loans=[loan_quarterly])

        manual_position_data_port.get_trackable_loans.return_value = [mpd]
        position_port.get_by_id.return_value = position_q
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(URL)
        assert response.status_code == 200
        quarterly_installment = _saved_loan(position_port).current_installment

        assert monthly_installment != quarterly_installment
