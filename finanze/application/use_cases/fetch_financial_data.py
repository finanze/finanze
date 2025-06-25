import asyncio
import logging
from asyncio import Lock
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from application.ports.historic_port import HistoricPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from dateutil.tz import tzlocal
from domain import native_entities
from domain.dezimal import Dezimal
from domain.entity import CredentialType, Entity, EntityType, Feature
from domain.entity_login import EntityLoginParams, LoginResultCode
from domain.exception.exceptions import EntityNotFound, ExecutionConflict
from domain.fetch_record import FetchRecord
from domain.fetch_result import (
    FETCH_BAD_LOGIN_CODES,
    FetchOptions,
    FetchRequest,
    FetchResult,
    FetchResultCode,
)
from domain.fetched_data import FetchedData
from domain.global_position import FactoringDetail, RealStateCFDetail
from domain.historic import BaseHistoricEntry, FactoringEntry, RealStateCFEntry
from domain.transactions import ProductType, TxType
from domain.use_cases.fetch_financial_data import FetchFinancialData

DEFAULT_FEATURES = [Feature.POSITION]


def compute_return_values(related_inv_txs):
    repayment_txs = [tx for tx in related_inv_txs if tx.type == TxType.REPAYMENT]
    interest_txs = [tx for tx in related_inv_txs if tx.type == TxType.INTEREST]
    dividend_txs = [tx for tx in related_inv_txs if tx.type == TxType.DIVIDEND]

    returned, repaid, fees, retentions, interests, net_return = (
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
    )
    last_return_tx = None

    if repayment_txs:
        fees += sum([tx.fees for tx in repayment_txs], start=Dezimal(0))
        retentions += sum([tx.retentions for tx in repayment_txs], start=Dezimal(0))
        interests += sum([tx.interests for tx in repayment_txs], start=Dezimal(0))

        repaid += sum([tx.amount for tx in repayment_txs], start=Dezimal(0))
        returned = repaid
        net_return = repaid

        last_return_tx = max(repayment_txs, key=lambda txx: txx.date)
        if last_return_tx:
            last_return_tx = last_return_tx.date

    if interest_txs:
        interest_fees = sum([tx.fees for tx in interest_txs], start=Dezimal(0))
        interest_retentions = sum(
            [tx.retentions for tx in interest_txs], start=Dezimal(0)
        )
        added_interests = sum([tx.interests for tx in interest_txs], start=Dezimal(0))

        fees += interest_fees
        retentions += interest_retentions
        interests += added_interests

        net_return += added_interests - interest_fees - interest_retentions
        returned += added_interests

    if dividend_txs:
        dividend_fees = sum([tx.fees for tx in dividend_txs], start=Dezimal(0))
        dividend_retentions = sum(
            [tx.retentions for tx in dividend_txs], start=Dezimal(0)
        )

        total_dividends = sum([tx.amount for tx in dividend_txs], start=Dezimal(0))

        fees += dividend_fees
        retentions += dividend_retentions
        interests += total_dividends

        net_return += total_dividends - dividend_fees - dividend_retentions
        returned += total_dividends

    return fees, interests, net_return, repaid, retentions, returned, last_return_tx


def _historic_inv_by_name(historical_position):
    investments_by_name = {}
    for key, cat in asdict(historical_position.investments).items():
        if not cat or "details" not in cat:
            continue
        investments = cat["details"]
        for inv in investments:
            inv_name = inv["name"]
            if inv_name in investments_by_name:
                investments_by_name[inv_name]["amount"] += inv["amount"]
                investments_by_name[inv_name]["last_invest_date"] = max(
                    investments_by_name[inv_name]["last_invest_date"],
                    inv["last_invest_date"],
                )
            else:
                investments_by_name[inv_name] = inv

    return investments_by_name


class FetchFinancialDataImpl(AtomicUCMixin, FetchFinancialData):
    def __init__(
        self,
        position_port: PositionPort,
        auto_contr_port: AutoContributionsPort,
        transaction_port: TransactionPort,
        historic_port: HistoricPort,
        entity_fetchers: dict[Entity, FinancialEntityFetcher],
        config_port: ConfigPort,
        credentials_port: CredentialsPort,
        sessions_port: SessionsPort,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._position_port = position_port
        self._auto_contr_repository = auto_contr_port
        self._transaction_port = transaction_port
        self._historic_port = historic_port
        self._entity_fetchers = entity_fetchers
        self._config_port = config_port
        self._credentials_port = credentials_port
        self._sessions_port = sessions_port
        self._last_fetches_port = last_fetches_port

        self._locks: dict[UUID, Lock] = {}

        self._log = logging.getLogger(__name__)

    def _get_lock(self, entity_id: UUID) -> Lock:
        if entity_id not in self._locks:
            self._locks[entity_id] = asyncio.Lock()
        return self._locks[entity_id]

    async def execute(self, fetch_request: FetchRequest) -> FetchResult:
        entity_id = fetch_request.entity_id

        entity = native_entities.get_native_by_id(
            entity_id, EntityType.FINANCIAL_INSTITUTION
        )
        if not entity:
            raise EntityNotFound(entity_id)

        features = fetch_request.features

        if features and not all(f in entity.features for f in features):
            return FetchResult(FetchResultCode.FEATURE_NOT_SUPPORTED)

        lock = self._get_lock(entity_id)

        if lock.locked():
            raise ExecutionConflict()

        async with lock:
            if Feature.POSITION in features:
                update_cooldown = self._get_position_update_cooldown()
                last_update = self._position_port.get_last_updated(entity_id)
                if (
                    last_update
                    and (datetime.now(tzlocal()) - last_update).seconds
                    < update_cooldown
                ):
                    remaining_seconds = (
                        update_cooldown
                        - (datetime.now(tzlocal()) - last_update).seconds
                    )
                    details = {
                        "lastUpdate": last_update.astimezone(tzlocal()).isoformat(),
                        "wait": remaining_seconds,
                    }
                    return FetchResult(FetchResultCode.COOLDOWN, details=details)

            credentials = self._credentials_port.get(entity.id)
            if not credentials:
                return FetchResult(FetchResultCode.NO_CREDENTIALS_AVAILABLE)

            for cred_name, cred_type in entity.credentials_template.items():
                if (
                    cred_type != CredentialType.INTERNAL
                    and cred_type != CredentialType.INTERNAL_TEMP
                    and cred_name not in credentials
                ):
                    return FetchResult(FetchResultCode.INVALID_CREDENTIALS)

            specific_fetcher = self._entity_fetchers[entity]

            stored_session = self._sessions_port.get(entity.id)
            login_request = EntityLoginParams(
                credentials=credentials,
                two_factor=fetch_request.two_factor,
                options=fetch_request.login_options,
                session=stored_session,
            )
            login_result = await specific_fetcher.login(login_request)
            login_result_code = login_result.code
            login_message = login_result.message

            if login_result_code == LoginResultCode.CODE_REQUESTED:
                return FetchResult(
                    FetchResultCode.CODE_REQUESTED,
                    details={
                        "message": login_message,
                        "processId": login_result.process_id,
                    },
                )

            elif login_result_code == LoginResultCode.MANUAL_LOGIN:
                return FetchResult(
                    FETCH_BAD_LOGIN_CODES[login_result_code],
                    details={"credentials": login_result.details},
                )

            elif login_result_code == LoginResultCode.LOGIN_REQUIRED:
                self._credentials_port.update_expiration(
                    entity.id, datetime.now(tzlocal())
                )
                return FetchResult(
                    FETCH_BAD_LOGIN_CODES[login_result_code],
                    details={"message": login_message},
                )

            elif login_result_code not in [
                LoginResultCode.CREATED,
                LoginResultCode.RESUMED,
            ]:
                return FetchResult(
                    FETCH_BAD_LOGIN_CODES[login_result_code],
                    details={"message": login_message},
                )

            elif login_result_code == LoginResultCode.CREATED:
                self._credentials_port.update_last_usage(entity.id)
                self._credentials_port.update_expiration(entity.id, None)

                session = login_result.session
                if session:
                    self._sessions_port.delete(entity.id)
                    self._sessions_port.save(entity.id, session)

            if not features:
                features = DEFAULT_FEATURES

            fetched_data = await self.get_data(
                entity, features, specific_fetcher, fetch_request.fetch_options
            )

            self._update_last_fetch(entity_id, features)

            return FetchResult(FetchResultCode.COMPLETED, data=fetched_data)

    async def get_data(
        self,
        entity: Entity,
        features: List[Feature],
        specific_fetcher: FinancialEntityFetcher,
        options: FetchOptions,
    ) -> FetchedData:
        position = None
        if Feature.POSITION in features:
            position = await specific_fetcher.global_position()

        auto_contributions = None
        if Feature.AUTO_CONTRIBUTIONS in features:
            auto_contributions = await specific_fetcher.auto_contributions()

        transactions = None
        if Feature.TRANSACTIONS in features:
            registered_txs = self._transaction_port.get_refs_by_entity(entity.id)
            transactions = await specific_fetcher.transactions(registered_txs, options)

        if position:
            self._position_port.save(position)

        if auto_contributions:
            self._auto_contr_repository.save(entity.id, auto_contributions)

        historic = None
        if transactions:
            self._transaction_port.save(transactions)

            if Feature.HISTORIC in features:
                entries = await self.build_historic(entity, specific_fetcher)

                self._historic_port.delete_by_entity(entity.id)
                self._historic_port.save(entries)

        fetched_data = FetchedData(
            position=position,
            auto_contributions=auto_contributions,
            transactions=transactions,
            historic=historic,
        )
        return fetched_data

    def _compute_historic_entry(
        self, entity, inv, txs_by_name
    ) -> Optional[BaseHistoricEntry]:
        inv_name = inv["name"]
        related_inv_txs = txs_by_name[inv_name]

        inv_txs = [tx for tx in related_inv_txs if tx.type == TxType.INVESTMENT]
        product_type = next((tx.product_type for tx in inv_txs), None)

        if product_type == ProductType.REAL_STATE_CF:
            inv = RealStateCFDetail(**inv)
        elif product_type == ProductType.FACTORING:
            inv = FactoringDetail(**inv)
        else:
            self._log.warning(
                f"Skipping investment with unsupported product type {product_type}"
            )
            return None

        fees, interests, net_return, repaid, retentions, returned, last_return_tx = (
            compute_return_values(related_inv_txs)
        )

        last_tx_date = max(related_inv_txs, key=lambda txx: txx.date).date

        historic_entry_base = {
            "id": uuid4(),
            "name": inv_name,
            "invested": inv.amount,
            "repaid": repaid,
            "returned": returned,
            "currency": inv.currency,
            "last_invest_date": inv.last_invest_date,
            "last_tx_date": last_tx_date,
            "effective_maturity": last_return_tx,
            "net_return": net_return,
            "fees": fees,
            "retentions": retentions,
            "interests": interests,
            "state": inv.state,
            "entity": entity,
            "product_type": product_type,
            "related_txs": related_inv_txs,
        }

        if product_type == ProductType.REAL_STATE_CF:
            return RealStateCFEntry(
                **historic_entry_base,
                interest_rate=Dezimal(inv.interest_rate),
                maturity=inv.maturity,
                extended_maturity=inv.extended_maturity,
                type=inv.type,
                business_type=inv.business_type,
            )

        elif product_type == ProductType.FACTORING:
            return FactoringEntry(
                **historic_entry_base,
                interest_rate=Dezimal(inv.interest_rate),
                gross_interest_rate=Dezimal(inv.gross_interest_rate),
                maturity=inv.maturity,
                type=inv.type,
            )

        return None

    async def build_historic(
        self, entity: Entity, specific_fetcher: FinancialEntityFetcher
    ) -> list[BaseHistoricEntry]:
        historical_position = await specific_fetcher.historical_position()

        investments_by_name = _historic_inv_by_name(historical_position)

        investments = list(investments_by_name.values())

        related_txs = self._transaction_port.get_by_entity(entity.id)
        txs_by_name = {}
        for tx in related_txs.investment:
            if tx.name in txs_by_name:
                txs_by_name[tx.name].append(tx)
            else:
                txs_by_name[tx.name] = [tx]

        historic_entries = []
        for inv in investments:
            inv_name = inv["name"]
            if inv_name not in txs_by_name:
                self._log.warning(f"No txs for investment {inv_name}")
                continue

            historic_entry = self._compute_historic_entry(entity, inv, txs_by_name)
            if historic_entry is None:
                continue

            historic_entries.append(historic_entry)

        return historic_entries

    def _get_position_update_cooldown(self) -> int:
        return self._config_port.load().fetch.updateCooldown

    def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        self._last_fetches_port.save(records)
