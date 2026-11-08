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
from application.ports.transaction_label_port import TransactionLabelPort
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
from domain.settings import (
    AccountAssetConfig,
    AccountExclusion,
    AssetConfig,
    CryptoAssetConfig,
    PartialSettings,
)
from domain.transactions import AccountTx, Transactions, TxType
from infrastructure.config.base_config import BASE_CONFIG


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
    config_port = AsyncMock()
    config_port.load_sections.return_value = BASE_CONFIG
    transaction_label_port = AsyncMock(spec=TransactionLabelPort)

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
        config_port,
        transaction_label_port,
    )
    use_case.mocks = {
        "external_entity_port": external_entity_port,
        "transaction_port": transaction_port,
        "transaction_labeler": transaction_labeler,
        "config_port": config_port,
        "transaction_label_port": transaction_label_port,
        "position_port": position_port,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("deep", [False, True])
async def test_external_exclusions_apply_before_save_and_deep_rebuild(deep):
    entity_id = uuid4()
    entity = _make_entity(entity_id)
    external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
    excluded, included = _movement(entity, "excluded"), _movement(entity, "included")
    excluded.iban, included.iban = "es12 34", "ES999"
    fetcher = _linked_fetcher(Transactions(account=[excluded, included, included]))
    use_case, _ = _build_use_case(external_entity, entity, fetcher)
    use_case.mocks["config_port"].load_sections.return_value = PartialSettings(
        assets=AssetConfig(
            crypto=CryptoAssetConfig(),
            accounts=AccountAssetConfig(
                [AccountExclusion(type="IBAN", value="ES1234")]
            ),
        )
    )
    port = use_case.mocks["transaction_port"]
    port.get_by_entity_and_source.return_value = Transactions(account=[])
    labels = use_case.mocks["transaction_label_port"]
    labels.get_classifications_by_ids.return_value = {}
    result = await use_case.execute(
        ExternalFetchRequest(
            external_entity_id=external_entity.id,
            features=[Feature.TRANSACTIONS],
            deep=deep,
        )
    )
    assert result.code == FetchResultCode.COMPLETED
    assert result.data.transactions.account == [included]
    assert port.save.await_args.args[0].account == [included]
    fetcher.global_position.assert_not_called()
    assert fetcher.transactions.await_args.args[0].registered_txs == (
        set() if deep else {"known"}
    )
    if deep:
        port.delete_by_entity_and_source.assert_awaited_once_with(
            entity_id, DataSource.REAL
        )
        port.get_latest_account_tx_date.assert_not_called()
        assert fetcher.transactions.await_args.args[
            0
        ].from_date == date.today() - timedelta(days=730)
    else:
        port.delete_by_entity_and_source.assert_not_called()


@pytest.mark.asyncio
async def test_external_deep_empty_result_clears_real_history():
    entity_id = uuid4()
    entity = _make_entity(entity_id)
    external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
    fetcher = _linked_fetcher(Transactions(account=[]))
    use_case, _ = _build_use_case(external_entity, entity, fetcher)
    port = use_case.mocks["transaction_port"]
    port.get_by_entity_and_source.return_value = Transactions(account=[])
    result = await use_case.execute(
        ExternalFetchRequest(
            external_entity_id=external_entity.id,
            features=[Feature.TRANSACTIONS],
            deep=True,
        )
    )
    assert result.code == FetchResultCode.COMPLETED
    port.delete_by_entity_and_source.assert_awaited_once_with(
        entity_id, DataSource.REAL
    )


@pytest.mark.asyncio
async def test_external_deep_failure_never_deletes_history():
    entity_id = uuid4()
    entity = _make_entity(entity_id)
    external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
    use_case, _ = _build_use_case(
        external_entity, entity, _linked_fetcher(tx_error=ExternalEntityFailed())
    )
    result = await use_case.execute(
        ExternalFetchRequest(
            external_entity_id=external_entity.id,
            features=[Feature.TRANSACTIONS],
            deep=True,
        )
    )
    assert result.code == FetchResultCode.REMOTE_FAILED
    use_case.mocks["transaction_port"].delete_by_entity_and_source.assert_not_called()


@pytest.mark.asyncio
async def test_external_position_only_does_not_delete_transactions_in_deep_mode():
    entity_id = uuid4()
    external_entity = _make_external_entity(entity_id, ExternalEntityStatus.LINKED)
    fetcher = _linked_fetcher(Transactions(account=[]))
    use_case, _ = _build_use_case(external_entity, _make_entity(entity_id), fetcher)
    result = await use_case.execute(
        ExternalFetchRequest(
            external_entity_id=external_entity.id,
            features=[Feature.POSITION],
            deep=True,
        )
    )
    assert result.details["completedFeatures"] == ["POSITION"]
    fetcher.transactions.assert_not_called()
    use_case.mocks["transaction_port"].delete_by_entity_and_source.assert_not_called()


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
