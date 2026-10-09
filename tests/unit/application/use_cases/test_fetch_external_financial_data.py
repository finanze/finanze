from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import ExternalEntityFetcher
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.use_cases.fetch_external_financial_data import (
    FetchExternalFinancialDataImpl,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.exception.exceptions import ExternalEntityFailed
from domain.external_entity import (
    ExternalEntity,
    ExternalEntityStatus,
    ExternalFetchRequest,
)
from domain.external_integration import ExternalIntegrationId
from domain.fetch_record import DataSource, FetchRecord
from domain.fetch_result import FetchResultCode
from domain.global_position import ProductType
from domain.labeling import LabelingTrigger
from domain.transactions import AccountTx, Transactions, TxType


def _build_use_case(external_entity, entity, fetcher=None, last_fetches=None):
    external_entity_port = AsyncMock(spec=ExternalEntityPort)
    external_entity_port.get_by_id = AsyncMock(return_value=external_entity)

    entity_port = AsyncMock(spec=EntityPort)
    entity_port.get_by_id = AsyncMock(return_value=entity)

    position_port = AsyncMock(spec=PositionPort)
    external_integration_port = AsyncMock(spec=ExternalIntegrationPort)
    external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
    last_fetches_port = AsyncMock(spec=LastFetchesPort)
    last_fetches_port.get_by_entity_id = AsyncMock(return_value=last_fetches)
    transaction_handler_port = MagicMock(spec=TransactionHandlerPort)
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=None)
    transaction_handler_port.start = MagicMock(return_value=tx_ctx)
    transaction_port = AsyncMock(spec=TransactionPort)
    transaction_port.get_latest_account_tx_date = AsyncMock(return_value=None)
    transaction_port.get_refs_by_entity = AsyncMock(return_value={"known"})
    transaction_labeler = AsyncMock(spec=TransactionLabeler)

    fetchers = {}
    if fetcher is not None:
        fetchers[ExternalIntegrationId.ENABLE_BANKING] = fetcher

    use_case = FetchExternalFinancialDataImpl(
        entity_port,
        external_entity_port,
        position_port,
        fetchers,
        external_integration_port,
        last_fetches_port,
        transaction_handler_port,
        transaction_port,
        transaction_labeler,
    )
    use_case.mocks = {
        "external_entity_port": external_entity_port,
        "transaction_port": transaction_port,
        "transaction_labeler": transaction_labeler,
    }
    return use_case, last_fetches_port


def _make_entity(entity_id):
    return Entity(
        id=entity_id,
        name="External Bank",
        natural_id="external-bank",
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.EXTERNALLY_PROVIDED,
        icon_url=None,
    )


def _make_external_entity(entity_id, status):
    return ExternalEntity(
        id=uuid4(),
        entity_id=entity_id,
        status=status,
        provider=ExternalIntegrationId.ENABLE_BANKING,
    )


class TestFetchExternalFinancialDataGuard:
    @pytest.mark.asyncio
    async def test_returns_link_expired_when_not_linked(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(
            entity_id, ExternalEntityStatus.UNLINKED
        )
        entity = _make_entity(entity_id)
        use_case, last_fetches_port = _build_use_case(external_entity, entity)

        result = await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert result.code == FetchResultCode.LINK_EXPIRED
        last_fetches_port.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_setup_provider_when_not_linked(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(entity_id, ExternalEntityStatus.ORPHAN)
        entity = _make_entity(entity_id)
        fetcher = MagicMock(spec=ExternalEntityFetcher)
        fetcher.setup = AsyncMock()
        fetcher.global_position = AsyncMock()
        use_case, last_fetches_port = _build_use_case(external_entity, entity, fetcher)

        result = await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert result.code == FetchResultCode.LINK_EXPIRED
        fetcher.setup.assert_not_called()
        fetcher.global_position.assert_not_called()
        last_fetches_port.save.assert_not_called()


def _linked_fetcher(transactions=None, tx_error=None):
    fetcher = MagicMock(spec=ExternalEntityFetcher)
    fetcher.setup = AsyncMock()
    fetcher.global_position = AsyncMock(return_value=None)
    if tx_error:
        fetcher.transactions = AsyncMock(side_effect=tx_error)
    else:
        fetcher.transactions = AsyncMock(return_value=transactions)
    return fetcher


def _movement(entity, ref):
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name="Movement",
        amount=Dezimal("10"),
        currency="EUR",
        type=TxType.OUTFLOW,
        date=datetime.now(tzlocal()),
        entity=entity,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
    )


class TestFetchExternalTransactions:
    @pytest.mark.asyncio
    async def test_saves_new_transactions_and_labels_them(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
        entity = _make_entity(entity_id)
        new_tx = _movement(entity, "new")
        fetcher = _linked_fetcher(
            Transactions(account=[new_tx, _movement(entity, "known")])
        )
        use_case, _ = _build_use_case(external_entity, entity, fetcher)

        result = await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert result.code == FetchResultCode.COMPLETED
        assert result.details["completedFeatures"] == ["POSITION", "TRANSACTIONS"]
        request = fetcher.transactions.await_args[0][0]
        assert request.from_date == date.today() - timedelta(days=730)
        saved = use_case.mocks["transaction_port"].save.await_args[0][0]
        assert [tx.ref for tx in saved.account] == ["new"]
        labeler = use_case.mocks["transaction_labeler"]
        assert labeler.classify.await_args[0][0].ids == [new_tx.id]
        assert labeler.classify_external.await_args[0][1] == LabelingTrigger.AUTO

    @pytest.mark.asyncio
    async def test_transaction_failure_is_partial_and_does_not_unlink(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
        entity = _make_entity(entity_id)
        fetcher = _linked_fetcher(tx_error=ExternalEntityFailed())
        use_case, _ = _build_use_case(external_entity, entity, fetcher)

        result = await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert result.code == FetchResultCode.PARTIALLY_COMPLETED
        assert result.details["failedFeatures"] == ["TRANSACTIONS"]
        use_case.mocks["external_entity_port"].update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_recent_transactions_fetch_is_skipped(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
        entity = _make_entity(entity_id)
        fetcher = _linked_fetcher(Transactions(account=[]))
        recent = FetchRecord(
            entity_id=entity_id,
            feature=Feature.TRANSACTIONS,
            date=datetime.now(tzlocal()) - timedelta(hours=1),
        )
        use_case, _ = _build_use_case(
            external_entity, entity, fetcher, last_fetches=[recent]
        )

        result = await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert result.code == FetchResultCode.COMPLETED
        fetcher.transactions.assert_not_called()

    @pytest.mark.asyncio
    async def test_position_fetched_weeks_ago_is_not_in_cooldown(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
        entity = _make_entity(entity_id)
        fetcher = _linked_fetcher(Transactions(account=[]))
        old = FetchRecord(
            entity_id=entity_id,
            feature=Feature.POSITION,
            date=datetime.now(tzlocal()) - timedelta(days=21, minutes=30),
        )
        use_case, _ = _build_use_case(
            external_entity, entity, fetcher, last_fetches=[old]
        )

        result = await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert result.code == FetchResultCode.COMPLETED
        fetcher.global_position.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_incremental_window_overlaps_latest_transaction(self):
        entity_id = uuid4()
        external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
        entity = _make_entity(entity_id)
        fetcher = _linked_fetcher(Transactions(account=[]))
        use_case, _ = _build_use_case(external_entity, entity, fetcher)
        use_case.mocks["transaction_port"].get_latest_account_tx_date = AsyncMock(
            return_value=datetime(2026, 9, 20, tzinfo=tzlocal())
        )

        await use_case.execute(
            ExternalFetchRequest(external_entity_id=external_entity.id)
        )

        assert fetcher.transactions.await_args[0][0].from_date == date(2026, 9, 15)
