from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.entity_port import EntityPort
from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_position_snapshot import ManualPositionSnapshotWriter
from application.use_cases.update_position import UpdatePositionImpl
from domain.crypto import CryptoAsset, CryptoAssetDetails, CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.external_integration import ExternalIntegrationId
from domain.fetch_record import DataSource
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
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

    real_estate_port = AsyncMock()
    loan_calculator = MagicMock(spec=LoanCalculatorPort)

    snapshot_writer = ManualPositionSnapshotWriter(
        position_port,
        manual_data_port,
        virtual_registry,
        real_estate_port,
        loan_calculator,
    )

    uc = UpdatePositionImpl(
        entity_port,
        position_port,
        crypto_registry,
        crypto_info,
        tx_handler,
        virtual_registry,
        snapshot_writer,
    )
    return (
        uc,
        entity_port,
        position_port,
        manual_data_port,
        virtual_registry,
        entity,
        real_estate_port,
    )


# ---------------------------------------------------------------------------
# TestSameDayDeletionGuard
# ---------------------------------------------------------------------------


class TestSameDayDeletionGuard:
    @pytest.mark.asyncio
    async def test_not_shared_deletes_old(self):
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
        # Empty records (default)
        request = _make_request(entity.id, products={})
        await uc.execute(request)

        position_port.save.assert_called_once()
        position_port.delete_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_clones_other_entity_imports(self):
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
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
        (
            uc,
            entity_port,
            position_port,
            manual_data_port,
            virtual_registry,
            entity,
            _,
        ) = _build_use_case()
        # No records at all
        request = _make_request(entity.id, products={})
        await uc.execute(request)

        manual_data_port.delete_by_position_id.assert_not_called()


# ---------------------------------------------------------------------------
# TestProcessCryptoAssets
# ---------------------------------------------------------------------------


def _build_crypto_use_case():
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

    snapshot_writer = ManualPositionSnapshotWriter(
        position_port,
        manual_data_port,
        virtual_registry,
        AsyncMock(),
        MagicMock(spec=LoanCalculatorPort),
    )

    uc = UpdatePositionImpl(
        entity_port,
        position_port,
        crypto_registry,
        crypto_info,
        tx_handler,
        virtual_registry,
        snapshot_writer,
    )
    return uc, crypto_registry, crypto_info


def _make_crypto_position(external_ids):
    asset = CryptoCurrencyPosition(
        id=None,
        symbol="GRAM",
        amount=Dezimal("654.234"),
        type=CryptoCurrencyType.TOKEN,
        crypto_asset=CryptoAsset(
            name="Gram (prev. Toncoin)",
            symbol="GRAM",
            icon_urls=[],
            external_ids=external_ids,
        ),
        contract_address="EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c",
    )
    wallet = CryptoCurrencyWallet(id=None, name="TON", assets=[asset])
    return GlobalPosition(
        id=uuid4(),
        entity=_make_entity(),
        date=datetime.now(tzlocal()),
        products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        source=DataSource.MANUAL,
    )


class TestProcessCryptoAssets:
    @pytest.mark.asyncio
    async def test_string_provider_converted_to_enum(self):
        uc, crypto_registry, crypto_info = _build_crypto_use_case()
        crypto_registry.get_by_symbol.return_value = None
        crypto_info.get_asset_details.return_value = CryptoAssetDetails(
            name="Gram (prev. Toncoin)",
            symbol="GRAM",
            platforms=[],
            provider=ExternalIntegrationId.COINGECKO,
            provider_id="the-open-network",
            price={},
            type=CryptoCurrencyType.TOKEN,
            icon_url="https://example.com/gram.png",
        )

        position = _make_crypto_position({"COINGECKO": "the-open-network"})
        await uc._process_crypto_assets_in_position(position)

        crypto_info.get_asset_details.assert_awaited_once()
        kwargs = crypto_info.get_asset_details.await_args.kwargs
        assert kwargs["provider"] == ExternalIntegrationId.COINGECKO
        assert isinstance(kwargs["provider"], ExternalIntegrationId)
        crypto_registry.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_provider_skips_without_error(self):
        uc, crypto_registry, crypto_info = _build_crypto_use_case()
        crypto_registry.get_by_symbol.return_value = None

        position = _make_crypto_position({"NOT_A_PROVIDER": "the-open-network"})
        await uc._process_crypto_assets_in_position(position)

        crypto_info.get_asset_details.assert_not_awaited()
        crypto_registry.save.assert_not_awaited()
