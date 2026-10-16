import logging
from asyncio import Lock
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
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
from domain.fetch_record import FetchRecord
from domain.fetch_result import (
    FetchedData,
    FetchResult,
    FetchResultCode,
)
from domain.labeling import LabelingTrigger
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

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            last_fetch = await self._last_fetches_port.get_by_entity_id(entity_id)
            result = handle_cooldown(
                [r for r in last_fetch or [] if r.feature == Feature.POSITION],
                self.EXTERNALLY_PROVIDED_POSITION_UPDATE_COOLDOWN,
            )
            if result:
                return result

            external_entity_provider = external_entity.provider
            provider = self._external_entity_fetchers[external_entity_provider]

            enabled_integrations = (
                await self._external_integration_port.get_payloads_by_type(
                    ExternalIntegrationType.ENTITY_PROVIDER
                )
            )
            await provider.setup(enabled_integrations)

            try:
                fetch_request = ExternalEntityFetchRequest(
                    external_entity=external_entity,
                    entity=entity,
                )
                position = await provider.global_position(fetch_request)

                async with self._transaction_handler_port.start():
                    if position:
                        await self._position_port.save(position)

                    await self._update_last_fetch(entity_id, [Feature.POSITION])

            except ExternalEntityFailed:
                return FetchResult(FetchResultCode.REMOTE_FAILED)
            except ExternalEntityLinkExpired:
                await self._external_entity_port.update_status(
                    external_entity_id, ExternalEntityStatus.UNLINKED
                )
                return FetchResult(FetchResultCode.LINK_EXPIRED)

            completed = [Feature.POSITION]
            failed = []
            transactions = None
            if self._transactions_due(last_fetch):
                try:
                    transactions = await self._fetch_and_store_transactions(
                        provider, external_entity, entity
                    )
                    completed.append(Feature.TRANSACTIONS)
                except FeatureNotSupported:
                    pass
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
                    FetchResultCode.PARTIALLY_COMPLETED, data=data, details=details
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
    ) -> Transactions:
        latest = await self._transaction_port.get_latest_account_tx_date(entity.id)
        if latest:
            from_date = latest.date() - timedelta(days=TRANSACTIONS_OVERLAP_DAYS)
        else:
            from_date = date.today() - timedelta(
                days=ACCOUNT_MOVEMENTS_MAX_LOOKBACK_DAYS
            )

        registered = await self._transaction_port.get_refs_by_entity(entity.id)
        transactions = await provider.transactions(
            ExternalEntityTxFetchRequest(
                external_entity=external_entity,
                entity=entity,
                from_date=from_date,
                registered_txs=registered,
            )
        )
        new_txs = []
        seen = set(registered)
        for tx in transactions.account or []:
            if tx.ref in seen:
                continue
            seen.add(tx.ref)
            new_txs.append(tx)

        new_ids = [tx.id for tx in new_txs]
        async with self._transaction_handler_port.start():
            if new_txs:
                await self._transaction_port.save(Transactions(account=new_txs))
                await self._transaction_labeler.classify(
                    AccountTxSelection(ids=new_ids)
                )
            await self._update_last_fetch(entity.id, [Feature.TRANSACTIONS])

        if new_ids:
            await self._transaction_labeler.classify_external(
                AccountTxSelection(ids=new_ids), LabelingTrigger.AUTO
            )
        return Transactions(investment=[], account=new_txs)

    async def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        await self._last_fetches_port.save(records)
