import asyncio
import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from finanze.app_core import MobileAppCore

_PYODIDE_PORT_CALL_LOCK = asyncio.Lock()


async def _pyodide_job_scheduler(jobs, timeout: float):
    start = time.monotonic()
    outcomes = []
    for job_factory, meta in jobs:
        if (time.monotonic() - start) >= timeout:
            break
        kind, inner_meta = meta
        try:
            res = await job_factory()
            outcomes.append((kind, inner_meta, res, None))
        except BaseException as e:
            outcomes.append((kind, inner_meta, None, e))
    return outcomes


async def _pyodide_port_call_runner(coro):
    async with _PYODIDE_PORT_CALL_LOCK:
        return await coro


class DeferredComponents:
    def __init__(self, core: "MobileAppCore"):
        self._core = core

    async def initialize(self):
        from domain import position_aggregation

        position_aggregation.add_extensions()

        import domain.native_entities
        from domain.backup import BackupFileType
        from domain.external_integration import ExternalIntegrationId
        from infrastructure.cloud.capacitor_cloud_data_register import (
            CapacitorCloudDataRegister,
        )
        from infrastructure.config.capacitor_config_adapter import (
            CapacitorConfigAdapter,
        )
        from infrastructure.file_storage.preference_exchange_storage import (
            PreferenceExchangeRateStorage,
        )
        from infrastructure.sheets.capacitor_sheets_initiator import (
            CapacitorSheetsInitiator,
        )
        from infrastructure.client.rates.crypto.preference_coingecko_strategy import (
            PreferenceCoinGeckoCacheStrategy,
        )
        from infrastructure.client.instrument.instrument_provider_adapter import (
            InstrumentProviderAdapter,
        )
        from infrastructure.client.rates.crypto.crypto_price_client import (
            CryptoAssetInfoClient,
        )
        from infrastructure.client.rates.exchange_rate_client import ExchangeRateClient
        from infrastructure.client.rates.metal.metal_price_client import (
            MetalPriceClient,
        )
        from infrastructure.client.cloud.backup.capacitor_file_transfer_strategy import (
            CapacitorFileTransferStrategy,
        )
        from infrastructure.client.cloud.backup.backup_client import BackupClient
        from infrastructure.repository.auto_contributions.auto_contributions_repository import (
            AutoContributionsSQLRepository as AutoContributionsRepository,
        )
        from infrastructure.repository.entity.entity_repository import (
            EntitySQLRepository as EntityRepository,
        )
        from infrastructure.repository.position.position_repository import (
            PositionSQLRepository as PositionRepository,
        )
        from infrastructure.repository.transaction.transaction_repository import (
            TransactionSQLRepository as TransactionRepository,
        )
        from infrastructure.repository.credentials.credentials_repository import (
            CredentialsRepository,
        )
        from infrastructure.repository.entity_account.entity_account_repository import (
            EntityAccountRepository,
        )
        from infrastructure.repository.crypto.crypto_wallet_repository import (
            CryptoWalletRepository,
        )
        from infrastructure.repository.db.transaction_handler import TransactionHandler
        from infrastructure.repository.earnings_expenses.pending_flow_repository import (
            PendingFlowRepository,
        )
        from infrastructure.repository.earnings_expenses.periodic_flow_repository import (
            PeriodicFlowRepository,
        )
        from infrastructure.repository.entity.external_entity_repository import (
            ExternalEntityRepository,
        )
        from infrastructure.repository.external_integration.external_integration_repository import (
            ExternalIntegrationRepository,
        )
        from infrastructure.repository.fetch.last_fetches_repository import (
            LastFetchesRepository,
        )
        from infrastructure.repository.position.manual_position_data_repository import (
            ManualPositionDataSQLRepository,
        )
        from infrastructure.repository.real_estate.real_estate_repository import (
            RealEstateRepository,
        )
        from infrastructure.repository.virtual.virtual_import_repository import (
            VirtualImportRepository,
        )
        from infrastructure.client.http.httpx_patch import apply_httpx_patch
        from infrastructure.calculations.loan_calculator import LoanCalculator
        from finanze.build_config import INCLUDE_CONNECTIONS
        from application.use_cases.get_available_entities import (
            GetAvailableEntitiesImpl,
        )
        from application.use_cases.get_backup_settings import GetBackupSettingsImpl
        from application.use_cases.get_backups import GetBackupsImpl
        from application.use_cases.get_cloud_auth import GetCloudAuthImpl
        from application.use_cases.get_contributions import GetContributionsImpl
        from application.use_cases.get_exchange_rates import GetExchangeRatesImpl
        from application.use_cases.get_external_integrations import (
            GetExternalIntegrationsImpl,
        )
        from application.use_cases.get_money_events import GetMoneyEventsImpl
        from application.use_cases.get_pending_flows import GetPendingFlowsImpl
        from application.use_cases.get_periodic_flows import GetPeriodicFlowsImpl
        from application.use_cases.get_position import GetPositionImpl
        from application.use_cases.get_transactions import GetTransactionsImpl
        from application.use_cases.get_settings import GetSettingsImpl
        from application.use_cases.handle_cloud_auth import HandleCloudAuthImpl
        from application.use_cases.list_real_estate import ListRealEstateImpl
        from application.use_cases.register_user import RegisterUserImpl
        from application.use_cases.user_login import UserLoginImpl
        from application.use_cases.change_user_password import ChangeUserPasswordImpl
        from application.use_cases.user_logout import UserLogoutImpl
        from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
        from application.use_cases.update_tracked_loans import UpdateTrackedLoansImpl

        core = self._core

        apply_httpx_patch()

        self.config_loader = CapacitorConfigAdapter()
        self.sheets_initiator = CapacitorSheetsInitiator()
        self.cloud_register = CapacitorCloudDataRegister()

        self.login = UserLoginImpl(
            core.db_manager,
            core.data_manager,
            self.config_loader,
            self.sheets_initiator,
            self.cloud_register,
        )
        self.register = RegisterUserImpl(
            core.db_manager,
            core.data_manager,
            self.config_loader,
            self.sheets_initiator,
            self.cloud_register,
        )
        self.get_settings = GetSettingsImpl(self.config_loader)

        db_client = core.db_client

        self.change_pw = ChangeUserPasswordImpl(core.db_manager, core.data_manager)
        self.logout = UserLogoutImpl(
            core.db_manager,
            self.config_loader,
            self.sheets_initiator,
            self.cloud_register,
        )

        if INCLUDE_CONNECTIONS:
            financial_entity_fetcher_stubs = {
                entity: True
                for entity in [
                    domain.native_entities.MY_INVESTOR,
                    domain.native_entities.TRADE_REPUBLIC,
                    domain.native_entities.URBANITAE,
                    domain.native_entities.WECITY,
                    domain.native_entities.SEGO,
                    domain.native_entities.MINTOS,
                    domain.native_entities.F24,
                    domain.native_entities.INDEXA_CAPITAL,
                    domain.native_entities.ING,
                    domain.native_entities.CAJAMAR,
                    domain.native_entities.UNICAJA,
                    domain.native_entities.IBKR,
                    domain.native_entities.BINANCE,
                    domain.native_entities.BITCOIN,
                    domain.native_entities.ETHEREUM,
                    domain.native_entities.LITECOIN,
                    domain.native_entities.TRON,
                    domain.native_entities.BSC,
                ]
            }
        else:
            financial_entity_fetcher_stubs = {}
        external_integrations = {
            ExternalIntegrationId.ETHERSCAN: True,
            ExternalIntegrationId.ETHPLORER: True,
        }

        self.position_repo = PositionRepository(client=db_client)
        self.manual_repo = ManualPositionDataSQLRepository(client=db_client)
        self.auto_repo = AutoContributionsRepository(client=db_client)
        self.tx_repo = TransactionRepository(client=db_client)
        self.entity_repo = EntityRepository(client=db_client)
        self.virtual_repo = VirtualImportRepository(client=db_client)
        self.wallet_repo = CryptoWalletRepository(client=db_client)
        self.last_fetches_repo = LastFetchesRepository(client=db_client)
        self.ext_int_repo = ExternalIntegrationRepository(client=db_client)
        self.period_repo = PeriodicFlowRepository(client=db_client)
        self.pending_repo = PendingFlowRepository(client=db_client)
        self.re_repo = RealEstateRepository(client=db_client)
        ext_ent_repo = ExternalEntityRepository(client=db_client)
        self.creds_repo = CredentialsRepository(client=db_client)
        self.entity_account_repo = EntityAccountRepository(client=db_client)
        ex_storage = PreferenceExchangeRateStorage()

        self.ex_client = ExchangeRateClient()
        self.crypto_info = CryptoAssetInfoClient(
            coingecko_strategy=PreferenceCoinGeckoCacheStrategy()
        )
        self.metal_client = MetalPriceClient()
        self.inst_provider = InstrumentProviderAdapter(
            enabled_clients=["ft", "yf", "finect", "tv", "ee", "le"]
        )

        self.tx_handler = TransactionHandler(client=db_client)

        file_transfer_strategy = CapacitorFileTransferStrategy()
        self.backup_repository = BackupClient(file_transfer_strategy)

        self.loan_calculator = LoanCalculator()

        self.get_avail_sources = GetAvailableEntitiesImpl(
            self.entity_repo,
            ext_ent_repo,
            self.creds_repo,
            self.wallet_repo,
            self.last_fetches_repo,
            self.virtual_repo,
            financial_entity_fetcher_stubs,
            {},
            self.entity_account_repo,
        )

        self.get_pos = GetPositionImpl(self.position_repo, self.entity_repo)
        self.get_contrib = GetContributionsImpl(self.auto_repo, self.entity_repo)
        self.get_tx = GetTransactionsImpl(self.tx_repo, self.entity_repo)
        self.get_ex_rates = GetExchangeRatesImpl(
            self.ex_client,
            self.crypto_info,
            self.metal_client,
            ex_storage,
            self.position_repo,
            port_call_runner=_pyodide_port_call_runner,
            job_scheduler=_pyodide_job_scheduler,
        )
        self.get_events = GetMoneyEventsImpl(
            self.get_contrib,
            GetPeriodicFlowsImpl(self.period_repo),
            GetPendingFlowsImpl(self.pending_repo),
            self.entity_repo,
            self.position_repo,
        )

        self.get_integrations = GetExternalIntegrationsImpl(
            self.ext_int_repo, external_integrations
        )

        self.get_periodic = GetPeriodicFlowsImpl(self.period_repo)
        self.get_pending = GetPendingFlowsImpl(self.pending_repo)

        self.list_re = ListRealEstateImpl(self.re_repo, self.position_repo)

        self.up_tracked = UpdateTrackedQuotesImpl(
            self.position_repo, self.manual_repo, self.inst_provider, self.ex_client
        )
        self.up_tracked_loans = UpdateTrackedLoansImpl(
            self.position_repo, self.manual_repo, self.loan_calculator, self.re_repo
        )

        backupable_ports = {
            BackupFileType.DATA: core.db_manager,
            BackupFileType.CONFIG: self.config_loader,
        }
        self.backupable_ports = backupable_ports
        self.get_backups = GetBackupsImpl(
            backupable_ports,
            self.backup_repository,
            self.cloud_register,
            self.cloud_register,
        )
        self.handle_cloud = HandleCloudAuthImpl(self.cloud_register)
        self.get_cloud = GetCloudAuthImpl(self.cloud_register)
        self.get_bkp_settings = GetBackupSettingsImpl(self.cloud_register)

        await ex_storage.initialize()
        await self.crypto_info.initialize()
        await self.get_ex_rates.execute(initial_load=True)
