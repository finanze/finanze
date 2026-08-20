import asyncio
import logging
import os
from asyncio import Lock
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.entity_account_port import EntityAccountPort
from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from application.ports.feature_flag_port import FeatureFlagPort
from application.ports.historic_port import HistoricPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.position_port import PositionPort
from application.ports.public_keychain_loader import PublicKeychainLoader
from application.ports.real_estate_port import RealEstatePort
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from dateutil.tz import tzlocal
from domain import native_entities
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityType, Feature
from domain.native_entity import CredentialType
from domain.entity_login import EntityLoginParams, LoginResultCode
from domain.exception.exceptions import EntityNotFound, ExecutionConflict
from domain.fetch_record import DataSource, FetchRecord
from domain.fetch_result import (
    FETCH_BAD_LOGIN_CODES,
    FetchedData,
    FetchOptions,
    FetchRequest,
    FetchResult,
    FetchResultCode,
)
from domain.global_position import (
    FactoringDetail,
    GlobalPosition,
    HistoricalPosition,
    ProductType,
    RealEstateCFDetail,
)
from domain.investment_returns import compute_return_values as _compute_return_values
from domain.loan_calculator import LoanCalculationParams
from domain.historic import (
    BaseHistoricEntry,
    FactoringEntry,
    Historic,
    RealEstateCFEntry,
)
from domain.transactions import TxType
from domain.use_cases.fetch_financial_data import FetchFinancialData

DEFAULT_FEATURES = [Feature.POSITION]
POSITION_UPDATE_COOLDOWN_SECONDS = int(
    os.environ.get("POSITION_UPDATE_COOLDOWN_SECONDS", 60)
)


def compute_return_values(related_inv_txs):
    return _compute_return_values(related_inv_txs)


def _historic_inv_by_name(historical_position):
    investments_by_name = {}
    for product_type, position in historical_position.positions.items():
        position = asdict(position)
        if not position or "entries" not in position:
            continue
        investments = position["entries"]
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


def handle_cooldown(last_fetches, update_cooldown) -> Optional[FetchResult]:
    last_fetch = None
    if last_fetches:
        last_fetch = last_fetches[0].date

    if last_fetch and (datetime.now(tzlocal()) - last_fetch).seconds < update_cooldown:
        remaining_seconds = (
            update_cooldown - (datetime.now(tzlocal()) - last_fetch).seconds
        )
        details = {
            "lastUpdate": last_fetch.astimezone(tzlocal()).isoformat(),
            "wait": remaining_seconds,
        }
        return FetchResult(FetchResultCode.COOLDOWN, details=details)

    return None


def split_features_by_cooldown(
    last_fetches,
    features: List[Feature],
    update_cooldown: int,
) -> tuple[List[Feature], Optional[FetchResult]]:
    now = datetime.now(tzlocal())
    last_by_feature: dict[Feature, datetime] = {}
    for record in last_fetches or []:
        existing = last_by_feature.get(record.feature)
        if existing is None or record.date > existing:
            last_by_feature[record.feature] = record.date

    pending: List[Feature] = []
    cooled_waits: List[int] = []
    cooled_last = None
    for feature in features:
        last_fetch = last_by_feature.get(feature)
        if last_fetch and (now - last_fetch).seconds < update_cooldown:
            cooled_waits.append(update_cooldown - (now - last_fetch).seconds)
            if cooled_last is None or last_fetch > cooled_last:
                cooled_last = last_fetch
        else:
            pending.append(feature)

    if features and not pending:
        details = {
            "lastUpdate": cooled_last.astimezone(tzlocal()).isoformat(),
            "wait": min(cooled_waits),
        }
        return [], FetchResult(FetchResultCode.COOLDOWN, details=details)

    return pending, None


class FetchFinancialDataImpl(FetchFinancialData):
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
        crypto_asset_registry_port: CryptoAssetRegistryPort,
        crypto_asset_info_provider: CryptoAssetInfoProvider,
        transaction_handler_port: TransactionHandlerPort,
        keychain_loader: PublicKeychainLoader,
        entity_account_port: EntityAccountPort,
        loan_calculator: LoanCalculatorPort,
        real_estate_port: RealEstatePort,
        feature_flag_port: FeatureFlagPort,
    ):
        self._position_port = position_port
        self._auto_contr_repository = auto_contr_port
        self._transaction_port = transaction_port
        self._historic_port = historic_port
        self._entity_fetchers = entity_fetchers
        self._config_port = config_port
        self._credentials_port = credentials_port
        self._sessions_port = sessions_port
        self._last_fetches_port = last_fetches_port
        self._crypto_asset_info_provider = crypto_asset_info_provider
        self._crypto_asset_registry_port = crypto_asset_registry_port
        self._transaction_handler_port = transaction_handler_port
        self._keychain_loader = keychain_loader
        self._entity_account_port = entity_account_port
        self._loan_calculator = loan_calculator
        self._real_estate_port = real_estate_port
        self._feature_flag_port = feature_flag_port

        self._locks: dict[UUID, Lock] = {}

        self._log = logging.getLogger(__name__)

    def _get_lock(self, entity_account_id: UUID) -> Lock:
        if entity_account_id not in self._locks:
            self._locks[entity_account_id] = asyncio.Lock()
        return self._locks[entity_account_id]

    async def execute(self, fetch_request: FetchRequest) -> FetchResult:
        entity_account_id = fetch_request.entity_account_id

        account = await self._entity_account_port.get_by_id(entity_account_id)
        if not account:
            return FetchResult(FetchResultCode.NOT_CONNECTED)

        entity = native_entities.get_native_by_id(
            account.entity_id,
            EntityType.FINANCIAL_INSTITUTION,
            EntityType.CRYPTO_EXCHANGE,
            EntityType.MARKET_FORECAST_PLATFORM,
        )
        if not entity:
            raise EntityNotFound(account.entity_id)

        features = fetch_request.features

        if features and not all(f in entity.features for f in features):
            return FetchResult(FetchResultCode.FEATURE_NOT_SUPPORTED)

        lock = self._get_lock(entity_account_id)

        if lock.locked():
            raise ExecutionConflict()

        async with lock:
            if not features:
                features = DEFAULT_FEATURES

            last_fetch = await self._last_fetches_port.get_by_entity_account_id(
                entity_account_id
            )
            features, cooldown_result = split_features_by_cooldown(
                last_fetch, features, POSITION_UPDATE_COOLDOWN_SECONDS
            )
            if cooldown_result:
                return cooldown_result

            credentials = await self._credentials_port.get(entity_account_id)
            # Incorporate any extra credentials from the request (e.g., for manual login)
            extra_credentials = fetch_request.credentials or {}
            for cred_name, cred_value in extra_credentials.items():
                credentials[cred_name] = cred_value

            if credentials is None:
                return FetchResult(FetchResultCode.NO_CREDENTIALS_AVAILABLE)

            for cred_name, cred_type in entity.credentials_template.items():
                if (
                    cred_type != CredentialType.INTERNAL
                    and cred_type != CredentialType.INTERNAL_TEMP
                    and cred_name not in credentials
                ):
                    return FetchResult(FetchResultCode.INVALID_CREDENTIALS)

            specific_fetcher = self._entity_fetchers[entity]

            keychain = await self._keychain_loader.load()

            stored_session = await self._sessions_port.get(entity_account_id)
            login_request = EntityLoginParams(
                credentials=credentials,
                two_factor=fetch_request.two_factor,
                options=fetch_request.login_options,
                session=stored_session,
                keychain=keychain,
                feature_flags=self._feature_flag_port.get_all(),
            )
            login_result = await specific_fetcher.login(login_request)
            login_result_code = login_result.code
            login_message = login_result.message
            details = login_result.details or {}

            if login_result_code == LoginResultCode.CODE_REQUESTED:
                details = {"message": login_message}
                if login_result.process_id:
                    details["processId"] = login_result.process_id
                if login_result.challenge_type:
                    details["challengeType"] = login_result.challenge_type
                login_details = login_result.details or {}
                if "challenge_domain" in login_details:
                    details["challengeDomain"] = login_details["challenge_domain"]
                return FetchResult(
                    FetchResultCode.CODE_REQUESTED,
                    details=details,
                    confirmation_type=login_result.confirmation_type,
                )

            elif login_result_code == LoginResultCode.MANUAL_LOGIN:
                return FetchResult(
                    FETCH_BAD_LOGIN_CODES[login_result_code],
                    details={"credentials": login_result.details},
                )

            elif login_result_code == LoginResultCode.LOGIN_REQUIRED:
                await self._sessions_port.delete(entity_account_id)
                await self._credentials_port.update_expiration(
                    entity_account_id, datetime.now(tzlocal())
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
                    details={"message": login_message, **details},
                )

            elif login_result_code == LoginResultCode.CREATED:
                await self._credentials_port.update_last_usage(entity_account_id)
                await self._credentials_port.update_expiration(entity_account_id, None)

                session = login_result.session
                if session:
                    await self._sessions_port.delete(entity_account_id)
                    await self._sessions_port.save(
                        entity_account_id, entity.id, session
                    )

            return await self.get_data(
                entity,
                features,
                specific_fetcher,
                fetch_request.fetch_options,
                entity_account_id=entity_account_id,
            )

    async def get_data(
        self,
        entity: Entity,
        features: List[Feature],
        specific_fetcher: FinancialEntityFetcher,
        options: FetchOptions,
        entity_account_id: UUID,
    ) -> FetchResult:
        completed: List[Feature] = []
        failed: List[Feature] = []
        last_error: Optional[Exception] = None

        position = None
        auto_contributions = None
        transactions = None
        historic = None
        transactions_ok = False

        if Feature.POSITION in features:
            try:
                position = await self._fetch_and_store_position(
                    entity, specific_fetcher, entity_account_id
                )
                completed.append(Feature.POSITION)
            except Exception as e:
                self._log.exception(e)
                failed.append(Feature.POSITION)
                last_error = e

        if Feature.AUTO_CONTRIBUTIONS in features:
            try:
                auto_contributions = await self._fetch_and_store_auto_contributions(
                    entity, specific_fetcher, entity_account_id
                )
                completed.append(Feature.AUTO_CONTRIBUTIONS)
            except Exception as e:
                self._log.exception(e)
                failed.append(Feature.AUTO_CONTRIBUTIONS)
                last_error = e

        if Feature.TRANSACTIONS in features:
            try:
                transactions = await self._fetch_and_store_transactions(
                    entity, specific_fetcher, options, entity_account_id
                )
                completed.append(Feature.TRANSACTIONS)
                transactions_ok = True
            except Exception as e:
                self._log.exception(e)
                failed.append(Feature.TRANSACTIONS)
                last_error = e

        if Feature.HISTORIC in features and transactions_ok and transactions:
            try:
                historic = await self._fetch_and_store_historic(
                    entity, specific_fetcher, entity_account_id
                )
                completed.append(Feature.HISTORIC)
            except Exception as e:
                self._log.exception(e)
                failed.append(Feature.HISTORIC)
                last_error = e

        if failed and not completed:
            if last_error is None:
                raise RuntimeError("All requested features failed")
            raise last_error

        data = FetchedData(
            position=position,
            auto_contributions=auto_contributions,
            transactions=transactions,
            historic=historic,
        )
        details = {
            "completedFeatures": [feature.value for feature in completed],
        }
        if failed:
            details["failedFeatures"] = [feature.value for feature in failed]
            return FetchResult(
                FetchResultCode.PARTIALLY_COMPLETED, data=data, details=details
            )
        return FetchResult(FetchResultCode.COMPLETED, data=data, details=details)

    async def _fetch_and_store_position(
        self,
        entity: Entity,
        specific_fetcher: FinancialEntityFetcher,
        entity_account_id: UUID,
    ) -> Optional[GlobalPosition]:
        position = await specific_fetcher.global_position()
        if not position:
            async with self._transaction_handler_port.start():
                await self._update_last_fetch(
                    entity.id, [Feature.POSITION], entity_account_id
                )
            return None

        position.entity_account_id = entity_account_id
        await self._enrich_crypto_assets(position)
        await self._enrich_loans(position)

        old_position_id = None
        if position.entity_account_id:
            old_position_id = await self._position_port.get_latest_real_position_id(
                position.entity_account_id
            )

        async with self._transaction_handler_port.start():
            await self._position_port.save(position)
            await self._migrate_stale_references(old_position_id, position)
            await self._sync_linked_loan_flows(position)
            await self._update_last_fetch(
                entity.id, [Feature.POSITION], entity_account_id
            )
        return position

    async def _fetch_and_store_auto_contributions(
        self,
        entity: Entity,
        specific_fetcher: FinancialEntityFetcher,
        entity_account_id: UUID,
    ):
        auto_contributions = await specific_fetcher.auto_contributions()
        if auto_contributions:
            for contrib in auto_contributions.periodic:
                contrib.entity_account_id = entity_account_id

        async with self._transaction_handler_port.start():
            if auto_contributions:
                await self._auto_contr_repository.save(
                    entity.id, auto_contributions, DataSource.REAL
                )
            await self._update_last_fetch(
                entity.id, [Feature.AUTO_CONTRIBUTIONS], entity_account_id
            )
        return auto_contributions

    async def _fetch_and_store_transactions(
        self,
        entity: Entity,
        specific_fetcher: FinancialEntityFetcher,
        options: FetchOptions,
        entity_account_id: UUID,
    ):
        registered_txs = {}
        if not options.deep:
            registered_txs = await self._transaction_port.get_refs_by_entity_account(
                entity_account_id
            )

        transactions = await specific_fetcher.transactions(registered_txs, options)

        if transactions:
            for tx in transactions.investment or []:
                tx.entity_account_id = entity_account_id
            for tx in transactions.account or []:
                tx.entity_account_id = entity_account_id

        async with self._transaction_handler_port.start():
            if options.deep:
                await self._transaction_port.delete_by_entity_account_id(
                    entity_account_id
                )
            if transactions:
                await self._transaction_port.save(transactions)
            await self._update_last_fetch(
                entity.id, [Feature.TRANSACTIONS], entity_account_id
            )
        return transactions

    async def _fetch_and_store_historic(
        self,
        entity: Entity,
        specific_fetcher: FinancialEntityFetcher,
        entity_account_id: UUID,
    ) -> Historic:
        historical_position = await specific_fetcher.historical_position()
        historic_entries = await self.build_historic(
            entity,
            historical_position,
            specific_fetcher,
            entity_account_id=entity_account_id,
        )
        historic = Historic(historic_entries)

        async with self._transaction_handler_port.start():
            await self._historic_port.delete_by_entity_account_id(entity_account_id)
            await self._historic_port.save(historic.entries)
            await self._update_last_fetch(
                entity.id, [Feature.HISTORIC], entity_account_id
            )
        return historic

    def _compute_historic_entry(
        self, entity, inv, txs_by_name, entity_account_id: UUID = None
    ) -> Optional[BaseHistoricEntry]:
        inv_name = inv["name"]
        related_inv_txs = txs_by_name[inv_name]

        inv_txs = [tx for tx in related_inv_txs if tx.type == TxType.INVESTMENT]
        product_type = next((tx.product_type for tx in inv_txs), None)

        if product_type == ProductType.REAL_ESTATE_CF:
            inv = RealEstateCFDetail(**inv)
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
        effective_maturity = (
            last_return_tx
            if (not hasattr(inv, "pending_amount") or inv.pending_amount == 0)
            else None
        )

        historic_entry_base = {
            "id": uuid4(),
            "name": inv_name,
            "invested": inv.amount,
            "repaid": repaid,
            "returned": returned,
            "currency": inv.currency,
            "last_invest_date": inv.last_invest_date,
            "last_tx_date": last_tx_date,
            "effective_maturity": effective_maturity,
            "net_return": net_return,
            "fees": fees,
            "retentions": retentions,
            "interests": interests,
            "state": inv.state,
            "entity": entity,
            "product_type": product_type,
            "related_txs": related_inv_txs,
            "entity_account_id": entity_account_id,
        }

        if product_type == ProductType.REAL_ESTATE_CF:
            return RealEstateCFEntry(
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
        self,
        entity: Entity,
        historical_position: HistoricalPosition,
        specific_fetcher: FinancialEntityFetcher,
        entity_account_id: UUID = None,
    ) -> list[BaseHistoricEntry]:
        investments_by_name = _historic_inv_by_name(historical_position)

        investments = list(investments_by_name.values())

        related_txs = await self._transaction_port.get_by_entity(entity.id)
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

            historic_entry = self._compute_historic_entry(
                entity, inv, txs_by_name, entity_account_id=entity_account_id
            )
            if historic_entry is None:
                continue

            historic_entries.append(historic_entry)

        return historic_entries

    async def _update_last_fetch(
        self,
        entity_id: UUID,
        features: List[Feature],
        entity_account_id: UUID,
    ):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(
                FetchRecord(
                    entity_id=entity_id,
                    feature=feature,
                    date=now,
                    entity_account_id=entity_account_id,
                )
            )
        await self._last_fetches_port.save(records)

    async def _enrich_crypto_assets(self, position: GlobalPosition):
        crypto_entries = position.products.get(ProductType.CRYPTO)
        if not crypto_entries:
            return

        for wallet_entry in crypto_entries.entries:
            for crypto_entry in wallet_entry.assets:
                asset_details = await self._crypto_asset_registry_port.get_by_symbol(
                    crypto_entry.symbol
                )
                if asset_details is None:
                    candidate_assets = (
                        await self._crypto_asset_info_provider.get_by_symbol(
                            crypto_entry.symbol
                        )
                    )
                    if candidate_assets:
                        asset_info = candidate_assets[0]
                        asset_info.id = uuid4()
                        await self._crypto_asset_registry_port.save(asset_info)
                        crypto_entry.crypto_asset = asset_info
                else:
                    crypto_entry.crypto_asset = asset_details

    async def _enrich_loans(self, position: GlobalPosition):
        loan_container = position.products.get(ProductType.LOAN)
        if not loan_container or not loan_container.entries:
            return

        for loan in loan_container.entries:
            if loan.installment_interests is not None:
                continue
            try:
                params = LoanCalculationParams(
                    loan_amount=None,
                    interest_rate=loan.interest_rate,
                    interest_type=loan.interest_type,
                    euribor_rate=loan.euribor_rate,
                    fixed_years=loan.fixed_years,
                    start=loan.creation,
                    end=loan.maturity,
                    principal_outstanding=loan.principal_outstanding,
                    fixed_interest_rate=loan.fixed_interest_rate,
                    installment_frequency=loan.installment_frequency,
                )
                result = await self._loan_calculator.calculate(params)
                loan.installment_interests = result.current_installment_interests
            except Exception:
                self._log.error(
                    "Could not compute installment_interests for loan %s %s",
                    loan.name,
                    loan.id,
                )

    async def _sync_linked_loan_flows(self, position: GlobalPosition):
        loans_container = position.products.get(ProductType.LOAN)
        if not loans_container:
            return
        for loan in loans_container.entries:
            await self._real_estate_port.sync_linked_loan_flows(loan)

    async def _migrate_stale_references(
        self,
        old_position_id,
        new_position: GlobalPosition,
    ):
        if old_position_id is None:
            return

        old_accounts = await self._position_port.get_account_iban_index(old_position_id)
        new_accounts_by_iban: dict[str, "UUID"] = {}
        accounts_container = new_position.products.get(ProductType.ACCOUNT)
        if accounts_container and hasattr(accounts_container, "entries"):
            for acc in accounts_container.entries:
                iban = getattr(acc, "iban", None)
                if iban and iban.strip():
                    new_accounts_by_iban[iban.strip()] = acc.id

        account_mapping = {}
        for old_id, old_iban in old_accounts.items():
            if not old_iban or not old_iban.strip():
                continue
            new_id = new_accounts_by_iban.get(old_iban.strip())
            if new_id and old_id != new_id:
                account_mapping[old_id] = new_id

        old_portfolios = await self._position_port.get_portfolio_name_index(
            old_position_id
        )
        new_portfolios_by_name: dict[str, "UUID"] = {}
        portfolios_container = new_position.products.get(ProductType.FUND_PORTFOLIO)
        if portfolios_container and hasattr(portfolios_container, "entries"):
            for pf in portfolios_container.entries:
                name = getattr(pf, "name", None)
                if name and name.strip():
                    new_portfolios_by_name[name.strip()] = pf.id

        portfolio_mapping = {}
        for old_id, old_name in old_portfolios.items():
            if not old_name or not old_name.strip():
                continue
            new_id = new_portfolios_by_name.get(old_name.strip())
            if new_id and old_id != new_id:
                portfolio_mapping[old_id] = new_id

        if account_mapping or portfolio_mapping:
            self._log.info(
                "Migrating stale references: %d account(s), %d portfolio(s)",
                len(account_mapping),
                len(portfolio_mapping),
            )
            await self._position_port.migrate_references(
                account_mapping, portfolio_mapping
            )
