import logging
from asyncio import Lock
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from application.use_cases.fetch_financial_data import handle_cooldown
from dateutil.tz import tzlocal
from domain.entity import Entity, EntityOrigin, Feature
from domain.exception.exceptions import (
    EntityNotFound,
    ExecutionConflict,
    ExternalEntityFailed,
    ExternalEntityLinkExpired,
    FeatureNotSupported,
)
from domain.external_entity import (
    ExternalEntity,
    ExternalEntityFetchRequest,
    ExternalEntityStatus,
    ExternalEntityTxFetchRequest,
    ExternalFetchRequest,
)
from domain.external_integration import (
    ExternalIntegrationId,
    ExternalIntegrationType,
)
from domain.fetch_exclusions import FetchExclusions
from domain.fetch_record import DataSource, FetchRecord
from domain.fetch_result import (
    FetchedData,
    FetchResult,
    FetchResultCode,
)
from domain.labeling import LabelingTrigger
from domain.settings import SettingsSection
from domain.transactions import (
    ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS,
    AccountTxSelection,
    Transactions,
)
from domain.use_cases.fetch_external_financial_data import FetchExternalFinancialData

TRANSACTIONS_OVERLAP_DAYS = 5


class FetchExternalFinancialDataImpl(FetchExternalFinancialData):
    EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN = 7200
    EXTERNALLY_PROVIDED_TRANSACTIONS_UPDATE_COOLDOWN = 6 * 3600

    def __init__(
        self,
        entity_port: EntityPort,
        external_entity_port: ExternalEntityPort,
        position_port: PositionPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        external_integration_port: ExternalIntegrationPort,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
        transaction_port: TransactionPort,
        transaction_labeler: TransactionLabeler,
        config_port: ConfigPort,
        transaction_label_port: TransactionLabelPort,
    ):
        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._position_port = position_port
        self._external_entity_fetchers = external_entity_fetchers
        self._external_integration_port = external_integration_port
        self._last_fetches_port = last_fetches_port
        self._transaction_handler_port = transaction_handler_port
        self._transaction_port = transaction_port
        self._transaction_labeler = transaction_labeler
        self._config_port = config_port
        self._transaction_label_port = transaction_label_port

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    async def execute(self, fetch_request: ExternalFetchRequest) -> FetchResult:
        external_entity_id = fetch_request.external_entity_id
        external_entity = await self._external_entity_port.get_by_id(external_entity_id)
        if not external_entity:
            raise EntityNotFound(external_entity_id)

        entity_id = external_entity.entity_id

        entity = await self._entity_port.get_by_id(entity_id)
        if not entity or entity.origin != EntityOrigin.EXTERNALLY_PROVIDED:
            raise EntityNotFound(entity_id)

        if external_entity.status != ExternalEntityStatus.LINKED:
            return FetchResult(FetchResultCode.LINK_EXPIRED)

        features = (
            fetch_request.features
            if fetch_request.features is not None
            else [Feature.POSITION, Feature.TRANSACTIONS]
        )
        if not features or any(
            feature not in (Feature.POSITION, Feature.TRANSACTIONS)
            for feature in features
        ):
            return FetchResult(FetchResultCode.FEATURE_NOT_SUPPORTED)

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            last_fetch = await self._last_fetches_port.get_by_entity_id(entity_id)
            if Feature.POSITION in features:
                result = handle_cooldown(
                    [r for r in last_fetch or [] if r.feature == Feature.POSITION],
                    self.EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN,
                )
                if result:
                    return result
            elif not self._transactions_due(last_fetch):
                result = handle_cooldown(
                    [r for r in last_fetch or [] if r.feature == Feature.TRANSACTIONS],
                    self.EXTERNALLY_PROVIDED_TRANSACTIONS_UPDATE_COOLDOWN,
                )
                if result:
                    return result

            settings = await self._config_port.load_sections({SettingsSection.ASSETS})
            if settings.assets is None:
                raise ValueError("Missing asset settings")
            exclusions = FetchExclusions(settings.assets.accounts.exclusions)

            external_entity_provider = external_entity.provider
            provider = self._external_entity_fetchers[external_entity_provider]

            enabled_integrations = (
                await self._external_integration_port.get_payloads_by_type(
                    ExternalIntegrationType.ENTITY_PROVIDER
                )
            )
            await provider.setup(enabled_integrations)

            position = None
            completed = []
            if Feature.POSITION in features:
                try:
                    position = await provider.global_position(
                        ExternalEntityFetchRequest(
                            external_entity=external_entity,
                            entity=entity,
                        )
                    )
                    if position:
                        exclusions.apply_to_position(position)

                    async with self._transaction_handler_port.start():
                        if position:
                            await self._position_port.save(position)
                        await self._update_last_fetch(entity_id, [Feature.POSITION])
                    completed.append(Feature.POSITION)
                except ExternalEntityFailed:
                    return FetchResult(FetchResultCode.REMOTE_FAILED)
                except ExternalEntityLinkExpired:
                    await self._external_entity_port.update_status(
                        external_entity_id, ExternalEntityStatus.UNLINKED
                    )
                    return FetchResult(FetchResultCode.LINK_EXPIRED)

            failed = []
            transactions = None
            if Feature.TRANSACTIONS in features and self._transactions_due(last_fetch):
                try:
                    transactions = await self._fetch_and_store_transactions(
                        provider,
                        external_entity,
                        entity,
                        exclusions,
                        fetch_request.deep,
                    )
                    completed.append(Feature.TRANSACTIONS)
                except FeatureNotSupported:
                    if not completed:
                        return FetchResult(FetchResultCode.FEATURE_NOT_SUPPORTED)
                except Exception as e:
                    self._log.warning(
                        f"Transactions fetch failed for external entity {external_entity_id}: {e}"
                    )
                    failed.append(Feature.TRANSACTIONS)

            data = FetchedData(position=position, transactions=transactions)
            details = {"completedFeatures": [f.value for f in completed]}
            if failed:
                details["failedFeatures"] = [f.value for f in failed]
                return FetchResult(
                    FetchResultCode.PARTIALLY_COMPLETED
                    if completed
                    else FetchResultCode.REMOTE_FAILED,
                    data=data,
                    details=details,
                )
            return FetchResult(FetchResultCode.COMPLETED, data=data, details=details)

    def _transactions_due(self, last_fetch: Optional[list[FetchRecord]]) -> bool:
        record = next(
            (r for r in last_fetch or [] if r.feature == Feature.TRANSACTIONS), None
        )
        if record is None:
            return True
        elapsed = (datetime.now(tzlocal()) - record.date).total_seconds()
        return elapsed >= self.EXTERNALLY_PROVIDED_TRANSACTIONS_UPDATE_COOLDOWN

    async def _fetch_and_store_transactions(
        self,
        provider: ExternalEntityFetcher,
        external_entity: ExternalEntity,
        entity: Entity,
        exclusions: FetchExclusions,
        deep: bool,
    ) -> Transactions:
        latest = (
            None
            if deep
            else await self._transaction_port.get_latest_account_tx_date(entity.id)
        )
        if latest:
            from_date = latest.date() - timedelta(days=TRANSACTIONS_OVERLAP_DAYS)
        else:
            from_date = date.today() - timedelta(
                days=ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS
            )

        registered = (
            set()
            if deep
            else await self._transaction_port.get_refs_by_entity(entity.id)
        )
        transactions = await provider.transactions(
            ExternalEntityTxFetchRequest(
                external_entity=external_entity,
                entity=entity,
                from_date=from_date,
                registered_txs=registered,
            )
        )
        exclusions.apply_to_transactions(transactions)
        new_txs = []
        seen = set(registered)
        for tx in transactions.account or []:
            if tx.ref in seen:
                continue
            seen.add(tx.ref)
            new_txs.append(tx)

        new_ids = [tx.id for tx in new_txs]
        previous = {}
        async with self._transaction_handler_port.start():
            if deep:
                existing = await self._transaction_port.get_by_entity_and_source(
                    entity.id, DataSource.REAL
                )
                existing_txs = existing.account or []
                classifications = (
                    await self._transaction_label_port.get_classifications_by_ids(
                        [tx.id for tx in existing_txs]
                    )
                )
                previous = {
                    (tx.entity.id, tx.ref): classifications[tx.id]
                    for tx in existing_txs
                    if tx.id in classifications
                }
                await self._transaction_port.delete_by_entity_and_source(
                    entity.id, DataSource.REAL
                )
            if new_txs:
                await self._transaction_port.save(Transactions(account=new_txs))
                if previous:
                    await self._transaction_label_port.restore(
                        {
                            tx.id: previous[(tx.entity.id, tx.ref)]
                            for tx in new_txs
                            if (tx.entity.id, tx.ref) in previous
                        }
                    )
                await self._transaction_labeler.classify(
                    AccountTxSelection(ids=new_ids)
                )
            await self._update_last_fetch(entity.id, [Feature.TRANSACTIONS])

        external_ids = [
            tx.id for tx in new_txs if (tx.entity.id, tx.ref) not in previous
        ]
        if external_ids:
            await self._transaction_labeler.classify_external(
                AccountTxSelection(ids=external_ids), LabelingTrigger.AUTO
            )
        return Transactions(investment=[], account=new_txs)

    async def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        await self._last_fetches_port.save(records)
