from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.entity_port import EntityPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.update_position import UpdatePositionImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    Deposit,
    Deposits,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    GlobalPosition,
    ProductType,
    UpdatePositionRequest,
)
from domain.virtual_data import VirtualDataImport, VirtualDataSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(id=None):
    return Entity(
        id=id or uuid4(),
        name="TestBank",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_request(entity_id, products=None):
    return UpdatePositionRequest(entity_id=entity_id, products=products or {})


def _make_import_record(import_id, gp_id, entity_id, dt, feature=Feature.POSITION):
    return VirtualDataImport(
        import_id=import_id,
        global_position_id=gp_id,
        source=VirtualDataSource.MANUAL,
        date=dt,
        feature=feature,
        entity_id=entity_id,
    )


def _build_use_case():
    entity_port = AsyncMock(spec=EntityPort)
    position_port = AsyncMock(spec=PositionPort)
    manual_data_port = AsyncMock(spec=ManualPositionDataPort)
    virtual_registry = AsyncMock(spec=VirtualImportRegistry)
    crypto_registry = AsyncMock(spec=CryptoAssetRegistryPort)
    crypto_info = AsyncMock(spec=CryptoAssetInfoProvider)
    tx_handler = MagicMock(spec=TransactionHandlerPort)

    @asynccontextmanager
    async def _fake_tx():
        yield

    tx_handler.start = _fake_tx

    entity = _make_entity()
    entity_port.get_by_id.return_value = entity
    position_port.get_last_grouped_by_entity.return_value = {}
    position_port.get_by_id.return_value = None
    virtual_registry.get_last_import_records.return_value = []

    uc = UpdatePositionImpl(
        entity_port,
        position_port,
        manual_data_port,
        virtual_registry,
        crypto_registry,
        crypto_info,
        tx_handler,
    )
    return uc, entity_port, position_port, manual_data_port, virtual_registry, entity


# ---------------------------------------------------------------------------
# TestSameDayDeletionGuard
# ---------------------------------------------------------------------------


class TestSameDayDeletionGuard:
    @pytest.mark.asyncio
    async def test_not_shared_deletes_old(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        now = datetime.now(tzlocal())
        import_id = uuid4()
        old_gp_id = uuid4()

        records = [
            _make_import_record(import_id, old_gp_id, entity.id, now),
        ]
        virtual_registry.get_last_import_records.return_value = records
        position_port.get_by_id.return_value = GlobalPosition(
            id=old_gp_id,
            entity=entity,
            date=now,
            products={},
            source=DataSource.MANUAL,
        )
        virtual_registry.is_position_shared.return_value = False

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        virtual_registry.is_position_shared.assert_called_once_with(
            old_gp_id, import_id
        )
        position_port.delete_by_id.assert_called_once_with(old_gp_id)

    @pytest.mark.asyncio
    async def test_shared_keeps_old(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        now = datetime.now(tzlocal())
        import_id = uuid4()
        old_gp_id = uuid4()

        records = [
            _make_import_record(import_id, old_gp_id, entity.id, now),
        ]
        virtual_registry.get_last_import_records.return_value = records
        position_port.get_by_id.return_value = GlobalPosition(
            id=old_gp_id,
            entity=entity,
            date=now,
            products={},
            source=DataSource.MANUAL,
        )
        virtual_registry.is_position_shared.return_value = True

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        virtual_registry.is_position_shared.assert_called_once_with(
            old_gp_id, import_id
        )
        position_port.delete_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_prior_just_saves(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        now = datetime.now(tzlocal())
        import_id = uuid4()
        other_entity_id = uuid4()

        # Record belongs to a different entity, so no prior_position_entry for our entity
        records = [
            _make_import_record(import_id, uuid4(), other_entity_id, now),
        ]
        virtual_registry.get_last_import_records.return_value = records

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        virtual_registry.is_position_shared.assert_not_called()
        position_port.save.assert_called_once()


# ---------------------------------------------------------------------------
# TestNewDayPath
# ---------------------------------------------------------------------------


class TestNewDayPath:
    @pytest.mark.asyncio
    async def test_new_day_does_not_delete_old(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        yesterday = datetime.now(tzlocal()) - timedelta(days=1)
        import_id = uuid4()
        old_gp_id = uuid4()

        records = [
            _make_import_record(import_id, old_gp_id, entity.id, yesterday),
        ]
        virtual_registry.get_last_import_records.return_value = records
        position_port.get_by_id.return_value = GlobalPosition(
            id=old_gp_id,
            entity=entity,
            date=yesterday,
            products={},
            source=DataSource.MANUAL,
        )

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        position_port.delete_by_id.assert_not_called()
        position_port.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_first_ever_just_saves(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        # Empty records (default)
        request = _make_request(entity.id, products={})
        await uc.execute(request)

        position_port.save.assert_called_once()
        position_port.delete_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_clones_other_entity_imports(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        yesterday = datetime.now(tzlocal()) - timedelta(days=1)
        import_id = uuid4()
        other1 = uuid4()
        other2 = uuid4()

        records = [
            _make_import_record(import_id, uuid4(), other1, yesterday),
            _make_import_record(import_id, uuid4(), other2, yesterday),
            _make_import_record(import_id, uuid4(), entity.id, yesterday),
        ]
        virtual_registry.get_last_import_records.return_value = records
        position_port.get_by_id.return_value = GlobalPosition(
            id=records[2].global_position_id,
            entity=entity,
            date=yesterday,
            products={},
            source=DataSource.MANUAL,
        )

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        virtual_registry.insert.assert_called_once()
        inserted = virtual_registry.insert.call_args[0][0]
        # 2 cloned from other entities + 1 new for this entity = 3
        assert len(inserted) == 3
        entity_ids_inserted = {e.entity_id for e in inserted}
        assert other1 in entity_ids_inserted
        assert other2 in entity_ids_inserted
        assert entity.id in entity_ids_inserted


# ---------------------------------------------------------------------------
# TestManualDataDeletion
# ---------------------------------------------------------------------------


class TestManualDataDeletion:
    @pytest.mark.asyncio
    async def test_deleted_when_prior_same_day(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        now = datetime.now(tzlocal())
        import_id = uuid4()
        old_gp_id = uuid4()

        records = [
            _make_import_record(import_id, old_gp_id, entity.id, now),
        ]
        virtual_registry.get_last_import_records.return_value = records
        position_port.get_by_id.return_value = GlobalPosition(
            id=old_gp_id,
            entity=entity,
            date=now,
            products={},
            source=DataSource.MANUAL,
        )
        virtual_registry.is_position_shared.return_value = False

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        manual_data_port.delete_by_position_id.assert_called_once_with(old_gp_id)

    @pytest.mark.asyncio
    async def test_deleted_when_prior_new_day(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        yesterday = datetime.now(tzlocal()) - timedelta(days=1)
        import_id = uuid4()
        old_gp_id = uuid4()

        records = [
            _make_import_record(import_id, old_gp_id, entity.id, yesterday),
        ]
        virtual_registry.get_last_import_records.return_value = records
        position_port.get_by_id.return_value = GlobalPosition(
            id=old_gp_id,
            entity=entity,
            date=yesterday,
            products={},
            source=DataSource.MANUAL,
        )

        request = _make_request(entity.id, products={})
        await uc.execute(request)

        manual_data_port.delete_by_position_id.assert_called_once_with(old_gp_id)

    @pytest.mark.asyncio
    async def test_not_deleted_when_no_prior(self):
        uc, entity_port, position_port, manual_data_port, virtual_registry, entity = (
            _build_use_case()
        )
        # No records at all
        request = _make_request(entity.id, products={})
        await uc.execute(request)

        manual_data_port.delete_by_position_id.assert_not_called()


# ---------------------------------------------------------------------------
# TestRegenerateSnapshotIds
# ---------------------------------------------------------------------------


def _make_global_position(products):
    entity = _make_entity()
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products=products,
        source=DataSource.MANUAL,
    )


class TestRegenerateSnapshotIds:
    def test_card_related_account_remapped(self):
        acc_id = uuid4()
        account = Account(
            id=acc_id, total=Dezimal(0), currency="EUR", type=AccountType.CHECKING
        )
        card = Card(
            id=uuid4(),
            currency="EUR",
            type=CardType.CREDIT,
            used=Dezimal(0),
            related_account=acc_id,
        )
        position = _make_global_position(
            {
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.CARD: Cards(entries=[card]),
            }
        )

        old_acc_id = account.id
        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert account.id != old_acc_id
        assert card.related_account == account.id

    def test_card_orphan_ref_unchanged(self):
        orphan_id = uuid4()
        card = Card(
            id=uuid4(),
            currency="EUR",
            type=CardType.CREDIT,
            used=Dezimal(0),
            related_account=orphan_id,
        )
        position = _make_global_position(
            {
                ProductType.CARD: Cards(entries=[card]),
            }
        )

        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert card.related_account == orphan_id

    def test_fund_portfolio_remapped(self):
        pf_id = uuid4()
        portfolio = FundPortfolio(id=pf_id, name="PF1")
        fund_portfolio_ref = FundPortfolio(id=pf_id, name="PF1")
        fund = FundDetail(
            id=uuid4(),
            name="Fund1",
            isin="XX",
            market=None,
            shares=Dezimal(10),
            market_value=Dezimal(1000),
            currency="EUR",
            type=FundType.MUTUAL_FUND,
            initial_investment=Dezimal(1000),
            portfolio=fund_portfolio_ref,
        )
        position = _make_global_position(
            {
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
                ProductType.FUND: FundInvestments(entries=[fund]),
            }
        )

        old_pf_id = portfolio.id
        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert portfolio.id != old_pf_id
        assert fund.portfolio.id == portfolio.id

    def test_fund_orphan_portfolio_unchanged(self):
        orphan_id = uuid4()
        fund_portfolio_ref = FundPortfolio(id=orphan_id, name="Orphan")
        fund = FundDetail(
            id=uuid4(),
            name="Fund1",
            isin="XX",
            market=None,
            shares=Dezimal(10),
            market_value=Dezimal(1000),
            currency="EUR",
            type=FundType.MUTUAL_FUND,
            initial_investment=Dezimal(1000),
            portfolio=fund_portfolio_ref,
        )
        position = _make_global_position(
            {
                ProductType.FUND: FundInvestments(entries=[fund]),
            }
        )

        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert fund.portfolio.id == orphan_id

    def test_portfolio_account_id_remapped(self):
        acc_id = uuid4()
        account = Account(
            id=acc_id,
            total=Dezimal(0),
            currency="EUR",
            type=AccountType.FUND_PORTFOLIO,
        )
        portfolio = FundPortfolio(id=uuid4(), name="PF1", account_id=acc_id)
        position = _make_global_position(
            {
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
            }
        )

        old_acc_id = account.id
        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert account.id != old_acc_id
        assert portfolio.account_id == account.id

    def test_portfolio_orphan_account_unchanged(self):
        orphan_id = uuid4()
        portfolio = FundPortfolio(id=uuid4(), name="PF1", account_id=orphan_id)
        position = _make_global_position(
            {
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
            }
        )

        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert portfolio.account_id == orphan_id

    def test_all_refs_valid_all_remapped(self):
        acc_id = uuid4()
        pf_id = uuid4()
        account = Account(
            id=acc_id,
            total=Dezimal(0),
            currency="EUR",
            type=AccountType.FUND_PORTFOLIO,
        )
        card = Card(
            id=uuid4(),
            currency="EUR",
            type=CardType.CREDIT,
            used=Dezimal(0),
            related_account=acc_id,
        )
        portfolio = FundPortfolio(id=pf_id, name="PF1", account_id=acc_id)
        fund_pf_ref = FundPortfolio(id=pf_id, name="PF1")
        fund = FundDetail(
            id=uuid4(),
            name="Fund1",
            isin="XX",
            market=None,
            shares=Dezimal(10),
            market_value=Dezimal(1000),
            currency="EUR",
            type=FundType.MUTUAL_FUND,
            initial_investment=Dezimal(1000),
            portfolio=fund_pf_ref,
        )
        position = _make_global_position(
            {
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.CARD: Cards(entries=[card]),
                ProductType.FUND_PORTFOLIO: FundPortfolios(entries=[portfolio]),
                ProductType.FUND: FundInvestments(entries=[fund]),
            }
        )

        old_acc_id = acc_id
        old_pf_id = pf_id
        UpdatePositionImpl._regenerate_snapshot_ids(position)

        # IDs changed
        assert account.id != old_acc_id
        assert portfolio.id != old_pf_id
        # Card remapped to new account id
        assert card.related_account == account.id
        # Portfolio remapped to new account id
        assert portfolio.account_id == account.id
        # Fund portfolio ref remapped
        assert fund.portfolio.id == portfolio.id

    def test_no_refs_no_issues(self):
        dep = Deposit(
            id=uuid4(),
            name="Test",
            amount=Dezimal(1000),
            currency="EUR",
            interest_rate=Dezimal("0.03"),
            creation=datetime.now(tzlocal()),
            maturity=datetime.now(tzlocal()).date(),
        )
        position = _make_global_position(
            {
                ProductType.DEPOSIT: Deposits(entries=[dep]),
            }
        )

        old_id = dep.id
        UpdatePositionImpl._regenerate_snapshot_ids(position)

        assert dep.id != old_id
