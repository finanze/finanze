import asyncio
import logging
import time

from infrastructure.controller.router import Router
from infrastructure.repository.db.capacitor_client import CapacitorDBClient
from infrastructure.file_storage.mobile_file_storage import MobileFileStorage
from infrastructure.file_storage.preference_exchange_storage import (
    PreferenceExchangeRateStorage,
)
from infrastructure.client.rates.crypto.preference_coingecko_strategy import (
    PreferenceCoinGeckoCacheStrategy,
)
from infrastructure.sheets.capacitor_sheets_initiator import CapacitorSheetsInitiator
from infrastructure.config.capacitor_config_adapter import CapacitorConfigAdapter
from infrastructure.repository.db.capacitor_db_manager import CapacitorDBManager
from infrastructure.user_files.capacitor_data_manager import (
    CapacitorSingleUserDataManager,
)
from infrastructure.config.capacitor_server_details_adapter import (
    CapacitorServerDetailsAdapter,
)
from infrastructure.client.http.httpx_patch import apply_httpx_patch
from infrastructure.client.entity.financial.tr.tr_websocket_patch import (
    apply_traderepublic_websocket_patch,
)

# Domain & Infra Imports
import domain.native_entities
from domain.backup import BackupFileType
from domain.export import FileFormat
from domain.external_integration import ExternalIntegrationId
from domain.platform import OS

from application.use_cases.add_entity_credentials import AddEntityCredentialsImpl
from application.use_cases.add_manual_transaction import AddManualTransactionImpl
from application.use_cases.calculate_loan import CalculateLoanImpl
from application.use_cases.calculate_savings import CalculateSavingsImpl
from application.use_cases.change_user_password import ChangeUserPasswordImpl
from application.use_cases.connect_crypto_wallet import ConnectCryptoWalletImpl
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.create_real_estate import CreateRealEstateImpl
from application.use_cases.create_template import CreateTemplateImpl
from application.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnectionImpl
from application.use_cases.delete_manual_transaction import DeleteManualTransactionImpl
from application.use_cases.delete_periodic_flow import DeletePeriodicFlowImpl
from application.use_cases.delete_real_estate import DeleteRealEstateImpl
from application.use_cases.delete_template import DeleteTemplateImpl
from application.use_cases.disconnect_entity import DisconnectEntityImpl
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.export_file import ExportFileImpl
from application.use_cases.fetch_crypto_data import FetchCryptoDataImpl
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from application.use_cases.forecast import ForecastImpl
from application.use_cases.get_available_entities import GetAvailableEntitiesImpl
from application.use_cases.get_backup_settings import GetBackupSettingsImpl
from application.use_cases.get_backups import GetBackupsImpl
from application.use_cases.get_cloud_auth import GetCloudAuthImpl
from application.use_cases.get_contributions import GetContributionsImpl
from application.use_cases.get_exchange_rates import GetExchangeRatesImpl
from application.use_cases.get_external_integrations import GetExternalIntegrationsImpl
from application.use_cases.get_historic import GetHistoricImpl
from application.use_cases.get_instrument_info import GetInstrumentInfoImpl
from application.use_cases.get_instruments import GetInstrumentsImpl
from application.use_cases.get_money_events import GetMoneyEventsImpl
from application.use_cases.get_pending_flows import GetPendingFlowsImpl
from application.use_cases.get_periodic_flows import GetPeriodicFlowsImpl
from application.use_cases.get_position import GetPositionImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.get_status import GetStatusImpl
from application.use_cases.get_template_fields import GetTemplateFieldsImpl
from application.use_cases.get_templates import GetTemplatesImpl
from application.use_cases.get_transactions import GetTransactionsImpl
from application.use_cases.handle_cloud_auth import HandleCloudAuthImpl
from application.use_cases.import_backup import ImportBackupImpl
from application.use_cases.import_file import ImportFileImpl
from application.use_cases.list_real_estate import ListRealEstateImpl
from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.save_backup_settings import SaveBackupSettingsImpl
from application.use_cases.save_commodities import SaveCommoditiesImpl
from application.use_cases.save_pending_flows import SavePendingFlowsImpl
from application.use_cases.save_periodic_flow import SavePeriodicFlowImpl
from application.use_cases.search_crypto_assets import SearchCryptoAssetsImpl
from application.use_cases.get_crypto_asset_details import GetCryptoAssetDetailsImpl
from application.use_cases.update_contributions import UpdateContributionsImpl
from application.use_cases.update_crypto_wallet import UpdateCryptoWalletConnectionImpl
from application.use_cases.update_manual_transaction import UpdateManualTransactionImpl
from application.use_cases.update_periodic_flow import UpdatePeriodicFlowImpl
from application.use_cases.update_position import UpdatePositionImpl
from application.use_cases.update_real_estate import UpdateRealEstateImpl
from application.use_cases.update_settings import UpdateSettingsImpl
from application.use_cases.update_template import UpdateTemplateImpl
from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
from application.use_cases.upload_backup import UploadBackupImpl
from application.use_cases.user_login import UserLoginImpl
from application.use_cases.user_logout import UserLogoutImpl

# Infra
from infrastructure.cloud.backup.capacitor_backup_processor import (
    CapacitorBackupProcessorAdapter,
)
from infrastructure.client.cloud.backup.capacitor_file_transfer_strategy import (
    CapacitorFileTransferStrategy,
)
from infrastructure.client.cloud.backup.backup_client import BackupClient
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient
from infrastructure.client.crypto.ethplorer.ethplorer_client import EthplorerClient
from infrastructure.client.entity.crypto.bitcoin.bitcoin_fetcher import BitcoinFetcher
from infrastructure.client.entity.crypto.bsc.bsc_fetcher import BSCFetcher
from infrastructure.client.entity.crypto.ethereum.ethereum_fetcher import (
    EthereumFetcher,
)
from infrastructure.client.entity.crypto.litecoin.litecoin_fetcher import (
    LitecoinFetcher,
)
from infrastructure.client.entity.crypto.tron.tron_fetcher import TronFetcher
from infrastructure.client.entity.financial.cajamar.cajamar_fetcher import (
    CajamarFetcher,
)
from infrastructure.client.entity.financial.f24.f24_fetcher import F24Fetcher
from infrastructure.client.entity.financial.indexa_capital.indexa_capital_fetcher import (
    IndexaCapitalFetcher,
)
from infrastructure.client.entity.financial.myinvestor import MyInvestorScraper
from infrastructure.client.entity.financial.sego.sego_fetcher import SegoFetcher
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    TradeRepublicFetcher,
)
from infrastructure.client.entity.financial.urbanitae.urbanitae_fetcher import (
    UrbanitaeFetcher,
)
from infrastructure.client.entity.financial.wecity.wecity_fetcher import WecityFetcher

from infrastructure.client.instrument.instrument_provider_adapter import (
    InstrumentProviderAdapter,
)
from infrastructure.client.rates.crypto.crypto_price_client import CryptoAssetInfoClient
from infrastructure.client.rates.exchange_rate_client import ExchangeRateClient
from infrastructure.client.rates.metal.metal_price_client import MetalPriceClient
from infrastructure.cloud.capacitor_cloud_data_register import (
    CapacitorCloudDataRegister,
)
from infrastructure.client.features.feature_flag_client import FeatureFlagClient
from infrastructure.repository import (
    AutoContributionsRepository,
    EntityRepository,
    HistoricRepository,
    PositionRepository,
    TransactionRepository,
)
from infrastructure.repository.credentials.credentials_repository import (
    CredentialsRepository,
)
from infrastructure.repository.crypto.crypto_asset_repository import (
    CryptoAssetRegistryRepository,
)
from infrastructure.repository.crypto.crypto_wallet_connection_repository import (
    CryptoWalletConnectionRepository,
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
from infrastructure.repository.sessions.sessions_repository import SessionsRepository
from infrastructure.repository.templates.template_repository import TemplateRepository
from infrastructure.repository.virtual.virtual_import_repository import (
    VirtualImportRepository,
)
from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
from infrastructure.templating.templated_data_generator import TemplatedDataGenerator
from infrastructure.templating.templated_data_parser import TemplateDataParser

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


class MobileApp:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self._router = Router()
        self.operative_system = None

    @property
    def router(self):
        return self._router

    async def initialize(self, operative_system: str | None = None):
        self.operative_system = (
            OS(operative_system.upper()) if operative_system else None
        )

        apply_traderepublic_websocket_patch()
        apply_httpx_patch()

        self.db_client = CapacitorDBClient()
        self.db_manager = CapacitorDBManager(self.db_client)
        self.data_manager = CapacitorSingleUserDataManager()
        self.config_loader = CapacitorConfigAdapter()
        self.sheets_initiator = CapacitorSheetsInitiator()

        self.cloud_register = CapacitorCloudDataRegister()
        self.etherscan_client = EtherscanClient()
        self.ethplorer_client = EthplorerClient()

        self.crypto_entity_fetchers = {
            domain.native_entities.BITCOIN: BitcoinFetcher(),
            domain.native_entities.ETHEREUM: EthereumFetcher(
                self.etherscan_client, self.ethplorer_client
            ),
            domain.native_entities.LITECOIN: LitecoinFetcher(),
            domain.native_entities.TRON: TronFetcher(),
            domain.native_entities.BSC: BSCFetcher(
                self.etherscan_client, self.ethplorer_client
            ),
        }
        self.financial_entity_fetchers = {
            domain.native_entities.MY_INVESTOR: MyInvestorScraper(),
            domain.native_entities.TRADE_REPUBLIC: TradeRepublicFetcher(),
            # domain.native_entities.UNICAJA: UnicajaFetcher(),
            domain.native_entities.URBANITAE: UrbanitaeFetcher(),
            domain.native_entities.WECITY: WecityFetcher(),
            domain.native_entities.SEGO: SegoFetcher(),
            domain.native_entities.F24: F24Fetcher(),
            domain.native_entities.INDEXA_CAPITAL: IndexaCapitalFetcher(),
            domain.native_entities.CAJAMAR: CajamarFetcher(),
        }
        self.external_integrations = {
            ExternalIntegrationId.ETHERSCAN: self.etherscan_client,
            ExternalIntegrationId.ETHPLORER: self.ethplorer_client,
        }

        csv_tsv_adapter = CSVFileTableAdapter()
        table_rw_adapter = TableRWDispatcher(
            {
                FileFormat.CSV: csv_tsv_adapter,
                FileFormat.TSV: csv_tsv_adapter,
                FileFormat.XLSX: XLSXFileTableAdapter(),
            }
        )

        # Repos
        position_repo = PositionRepository(client=self.db_client)
        manual_repo = ManualPositionDataSQLRepository(client=self.db_client)
        auto_repo = AutoContributionsRepository(client=self.db_client)
        tx_repo = TransactionRepository(client=self.db_client)
        historic_repo = HistoricRepository(client=self.db_client)
        entity_repo = EntityRepository(client=self.db_client)
        sessions_repo = SessionsRepository(client=self.db_client)
        virtual_repo = VirtualImportRepository(client=self.db_client)
        wallet_repo = CryptoWalletConnectionRepository(client=self.db_client)
        crypto_asset_repo = CryptoAssetRegistryRepository(client=self.db_client)
        last_fetches_repo = LastFetchesRepository(client=self.db_client)
        ext_int_repo = ExternalIntegrationRepository(client=self.db_client)
        period_repo = PeriodicFlowRepository(client=self.db_client)
        pending_repo = PendingFlowRepository(client=self.db_client)
        re_repo = RealEstateRepository(client=self.db_client)
        ext_ent_repo = ExternalEntityRepository(client=self.db_client)
        temp_repo = TemplateRepository(client=self.db_client)
        creds_repo = CredentialsRepository(client=self.db_client)

        file_storage = MobileFileStorage()
        ex_storage = PreferenceExchangeRateStorage()

        ex_client = ExchangeRateClient()
        crypto_info = CryptoAssetInfoClient(
            coingecko_strategy=PreferenceCoinGeckoCacheStrategy()
        )
        metal_client = MetalPriceClient()
        inst_provider = InstrumentProviderAdapter(
            enabled_clients=["ft", "finect", "tv", "ee"]
        )

        tx_handler = TransactionHandler(client=self.db_client)

        template_gen = TemplatedDataGenerator()
        template_parser = TemplateDataParser()

        backup_processor = CapacitorBackupProcessorAdapter()
        file_transfer_strategy = CapacitorFileTransferStrategy()
        backup_repository = BackupClient(file_transfer_strategy)

        # UCs
        self.login = UserLoginImpl(
            self.db_manager,
            self.data_manager,
            self.config_loader,
            self.sheets_initiator,
            self.cloud_register,
        )
        self.register = RegisterUserImpl(
            self.db_manager,
            self.data_manager,
            self.config_loader,
            self.sheets_initiator,
            self.cloud_register,
        )
        self.change_pw = ChangeUserPasswordImpl(self.db_manager, self.data_manager)
        self.logout = UserLogoutImpl(
            self.db_manager,
            self.config_loader,
            self.sheets_initiator,
            self.cloud_register,
        )

        users = await self.data_manager.get_users()
        ff_client = FeatureFlagClient(users, self.operative_system)
        server_details = CapacitorServerDetailsAdapter()
        self.status = GetStatusImpl(
            self.db_manager,
            self.data_manager,
            server_details,
            ff_client,
        )
        self.get_settings = GetSettingsImpl(self.config_loader)
        self.update_settings = UpdateSettingsImpl(self.config_loader)

        self.get_avail_sources = GetAvailableEntitiesImpl(
            entity_repo,
            ext_ent_repo,
            creds_repo,
            wallet_repo,
            last_fetches_repo,
            virtual_repo,
            self.financial_entity_fetchers,
            {},
        )
        self.add_entity_creds = AddEntityCredentialsImpl(
            self.financial_entity_fetchers, creds_repo, sessions_repo, tx_handler
        )
        self.disconnect_entity = DisconnectEntityImpl(
            creds_repo, sessions_repo, tx_handler
        )

        self.fetch_financial = FetchFinancialDataImpl(
            position_repo,
            auto_repo,
            tx_repo,
            historic_repo,
            self.financial_entity_fetchers,
            self.config_loader,
            creds_repo,
            sessions_repo,
            last_fetches_repo,
            crypto_asset_repo,
            crypto_info,
            tx_handler,
        )
        self.fetch_crypto = FetchCryptoDataImpl(
            position_repo,
            self.crypto_entity_fetchers,
            wallet_repo,
            crypto_asset_repo,
            crypto_info,
            last_fetches_repo,
            ext_int_repo,
            tx_handler,
        )
        self.import_file = ImportFileImpl(
            position_repo,
            tx_repo,
            table_rw_adapter,
            entity_repo,
            virtual_repo,
            temp_repo,
            template_parser,
            tx_handler,
        )
        self.export_file = ExportFileImpl(
            position_repo,
            auto_repo,
            tx_repo,
            historic_repo,
            entity_repo,
            temp_repo,
            template_gen,
            table_rw_adapter,
        )

        self.get_pos = GetPositionImpl(position_repo, entity_repo)
        self.get_contrib = GetContributionsImpl(auto_repo, entity_repo)
        self.get_tx = GetTransactionsImpl(tx_repo, entity_repo)
        self.get_ex_rates = GetExchangeRatesImpl(
            ex_client,
            crypto_info,
            metal_client,
            ex_storage,
            position_repo,
            port_call_runner=_pyodide_port_call_runner,
            job_scheduler=_pyodide_job_scheduler,
        )
        self.get_events = GetMoneyEventsImpl(
            self.get_contrib,
            GetPeriodicFlowsImpl(period_repo),
            GetPendingFlowsImpl(pending_repo),
            entity_repo,
            position_repo,
        )

        self.conn_crypto = ConnectCryptoWalletImpl(
            wallet_repo, self.crypto_entity_fetchers, ext_int_repo
        )
        self.up_crypto = UpdateCryptoWalletConnectionImpl(wallet_repo)
        self.del_crypto = DeleteCryptoWalletConnectionImpl(wallet_repo)

        self.save_commodities = SaveCommoditiesImpl(
            position_repo, ex_client, metal_client, last_fetches_repo, tx_handler
        )

        self.get_integrations = GetExternalIntegrationsImpl(ext_int_repo)
        self.conn_integration = ConnectExternalIntegrationImpl(
            ext_int_repo, self.external_integrations
        )
        self.disconn_integration = DisconnectExternalIntegrationImpl(ext_int_repo)

        self.save_periodic = SavePeriodicFlowImpl(period_repo)
        self.up_periodic = UpdatePeriodicFlowImpl(period_repo)
        self.del_periodic = DeletePeriodicFlowImpl(period_repo)
        self.get_periodic = GetPeriodicFlowsImpl(period_repo)
        self.save_pending = SavePendingFlowsImpl(pending_repo, tx_handler)
        self.get_pending = GetPendingFlowsImpl(pending_repo)

        self.list_re = ListRealEstateImpl(re_repo)
        self.create_re = CreateRealEstateImpl(
            re_repo, period_repo, tx_handler, file_storage
        )
        self.up_re = UpdateRealEstateImpl(
            re_repo, period_repo, tx_handler, file_storage
        )
        self.del_re = DeleteRealEstateImpl(
            re_repo, period_repo, tx_handler, file_storage
        )

        self.calc_loan = CalculateLoanImpl()
        self.forecast = ForecastImpl(
            position_repo, auto_repo, period_repo, pending_repo, re_repo, entity_repo
        )

        self.up_contrib = UpdateContributionsImpl(
            entity_repo, auto_repo, virtual_repo, tx_handler
        )
        self.up_pos = UpdatePositionImpl(
            entity_repo,
            position_repo,
            manual_repo,
            virtual_repo,
            crypto_asset_repo,
            crypto_info,
            tx_handler,
        )
        self.add_manual_tx = AddManualTransactionImpl(
            entity_repo, tx_repo, virtual_repo, tx_handler
        )
        self.up_manual_tx = UpdateManualTransactionImpl(
            entity_repo, tx_repo, virtual_repo, tx_handler
        )
        self.del_manual_tx = DeleteManualTransactionImpl(
            tx_repo, virtual_repo, tx_handler
        )

        self.get_historic = GetHistoricImpl(historic_repo, entity_repo)
        self.get_instruments = GetInstrumentsImpl(inst_provider)
        self.get_inst_info = GetInstrumentInfoImpl(inst_provider)
        self.search_crypto = SearchCryptoAssetsImpl(crypto_info)
        self.get_crypto_details = GetCryptoAssetDetailsImpl(crypto_info, entity_repo)
        self.up_tracked = UpdateTrackedQuotesImpl(
            position_repo, manual_repo, inst_provider, ex_client
        )

        self.get_tmpl = GetTemplatesImpl(temp_repo)
        self.create_tmpl = CreateTemplateImpl(temp_repo)
        self.up_tmpl = UpdateTemplateImpl(temp_repo)
        self.del_tmpl = DeleteTemplateImpl(temp_repo)
        self.get_tmpl_fields = GetTemplateFieldsImpl()

        self.calc_savings = CalculateSavingsImpl()
        backupable_ports = {
            BackupFileType.DATA: self.db_manager,
            BackupFileType.CONFIG: self.config_loader,
        }
        self.upload_backup = UploadBackupImpl(
            self.db_manager,
            backupable_ports,
            backup_processor,
            backup_repository,
            self.cloud_register,
            self.cloud_register,
        )
        self.import_backup = ImportBackupImpl(
            self.db_manager,
            backupable_ports,
            backup_processor,
            backup_repository,
            self.cloud_register,
            self.cloud_register,
        )
        self.get_backups = GetBackupsImpl(
            backupable_ports,
            backup_repository,
            self.cloud_register,
            self.cloud_register,
        )
        self.handle_cloud = HandleCloudAuthImpl(self.cloud_register)
        self.get_cloud = GetCloudAuthImpl(self.cloud_register)
        self.get_bkp_settings = GetBackupSettingsImpl(self.cloud_register)
        self.save_bkp_settings = SaveBackupSettingsImpl(self.cloud_register)

        await ff_client.load()

        self.setup_routes()

        await ex_storage.initialize()
        await crypto_info.initialize()

        print("MobileApp Initialized with Full Routing")

    def setup_routes(self):
        from importlib import import_module

        r = self.router
        module_cache = {}

        def bind(module_name, func_name, *deps):
            if module_name not in module_cache:
                module_cache[module_name] = import_module(
                    f"infrastructure.controller.routes.{module_name}"
                )
            func = getattr(module_cache[module_name], func_name)

            async def handler(_req):
                view_args = getattr(_req, "view_args", None) or {}
                return await func(*deps, **view_args)

            return handler

        route_map = [
            ("POST", "/api/v1/login", "user_login", "user_login", self.login),
            ("POST", "/api/v1/signup", "register_user", "register_user", self.register),
            (
                "POST",
                "/api/v1/change-password",
                "change_user_password",
                "change_user_password",
                self.change_pw,
            ),
            ("GET", "/api/v1/status", "get_status", "status", self.status),
            ("POST", "/api/v1/logout", "logout", "logout", self.logout),
            (
                "GET",
                "/api/v1/settings",
                "get_settings",
                "get_settings",
                self.get_settings,
            ),
            (
                "POST",
                "/api/v1/settings",
                "update_settings",
                "update_settings",
                self.update_settings,
            ),
            (
                "GET",
                "/api/v1/entities",
                "get_available_sources",
                "get_available_sources",
                self.get_avail_sources,
            ),
            (
                "POST",
                "/api/v1/entities/login",
                "add_entity_login",
                "add_entity_login",
                self.add_entity_creds,
            ),
            (
                "DELETE",
                "/api/v1/entities/login",
                "disconnect_entity",
                "disconnect_entity",
                self.disconnect_entity,
            ),
            (
                "POST",
                "/api/v1/data/fetch/financial",
                "fetch_financial_data",
                "fetch_financial_data",
                self.fetch_financial,
            ),
            (
                "POST",
                "/api/v1/data/fetch/crypto",
                "fetch_crypto_data",
                "fetch_crypto_data",
                self.fetch_crypto,
            ),
            (
                "POST",
                "/api/v1/data/import/file",
                "import_file",
                "import_file_route",
                self.import_file,
            ),
            (
                "POST",
                "/api/v1/data/export/file",
                "export_file",
                "export_file",
                self.export_file,
            ),
            ("GET", "/api/v1/positions", "positions", "positions", self.get_pos),
            (
                "GET",
                "/api/v1/contributions",
                "contributions",
                "contributions",
                self.get_contrib,
            ),
            (
                "GET",
                "/api/v1/transactions",
                "transactions",
                "transactions",
                self.get_tx,
            ),
            (
                "GET",
                "/api/v1/exchange-rates",
                "exchange_rates",
                "exchange_rates",
                self.get_ex_rates,
            ),
            (
                "GET",
                "/api/v1/events",
                "get_money_events",
                "get_money_events",
                self.get_events,
            ),
            (
                "POST",
                "/api/v1/crypto-wallet",
                "connect_crypto_wallet",
                "connect_crypto_wallet",
                self.conn_crypto,
            ),
            (
                "PUT",
                "/api/v1/crypto-wallet",
                "update_crypto_wallet",
                "update_crypto_wallet",
                self.up_crypto,
            ),
            (
                "DELETE",
                "/api/v1/crypto-wallet/<wallet_connection_id>",
                "delete_crypto_wallet",
                "delete_crypto_wallet",
                self.del_crypto,
            ),
            (
                "POST",
                "/api/v1/commodities",
                "save_commodities",
                "save_commodities",
                self.save_commodities,
            ),
            (
                "GET",
                "/api/v1/integrations",
                "get_external_integrations",
                "get_external_integrations",
                self.get_integrations,
            ),
            (
                "POST",
                "/api/v1/integrations/<integration_id>",
                "connect_external_integration",
                "connect_external_integration",
                self.conn_integration,
            ),
            (
                "DELETE",
                "/api/v1/integrations/<integration_id>",
                "disconnect_external_integration",
                "disconnect_external_integration",
                self.disconn_integration,
            ),
            (
                "POST",
                "/api/v1/flows/periodic",
                "save_periodic_flow",
                "save_periodic_flow",
                self.save_periodic,
            ),
            (
                "PUT",
                "/api/v1/flows/periodic",
                "update_periodic_flow",
                "update_periodic_flow",
                self.up_periodic,
            ),
            (
                "DELETE",
                "/api/v1/flows/periodic/<flow_id>",
                "delete_periodic_flow",
                "delete_periodic_flow",
                self.del_periodic,
            ),
            (
                "GET",
                "/api/v1/flows/periodic",
                "get_periodic_flows",
                "get_periodic_flows",
                self.get_periodic,
            ),
            (
                "POST",
                "/api/v1/flows/pending",
                "save_pending_flows",
                "save_pending_flows",
                self.save_pending,
            ),
            (
                "GET",
                "/api/v1/flows/pending",
                "get_pending_flows",
                "get_pending_flows",
                self.get_pending,
            ),
            (
                "GET",
                "/api/v1/real-estate",
                "list_real_estate",
                "list_real_estate",
                self.list_re,
            ),
            (
                "POST",
                "/api/v1/real-estate",
                "create_real_estate",
                "create_real_estate",
                self.create_re,
            ),
            (
                "PUT",
                "/api/v1/real-estate",
                "update_real_estate",
                "update_real_estate",
                self.up_re,
            ),
            (
                "DELETE",
                "/api/v1/real-estate/<real_estate_id>",
                "delete_real_estate",
                "delete_real_estate",
                self.del_re,
            ),
            (
                "POST",
                "/api/v1/calculation/loan",
                "calculate_loan",
                "calculate_loan",
                self.calc_loan,
            ),
            ("POST", "/api/v1/forecast", "forecast", "forecast", self.forecast),
            (
                "POST",
                "/api/v1/data/manual/contributions",
                "update_contributions",
                "update_contributions",
                self.up_contrib,
            ),
            (
                "POST",
                "/api/v1/data/manual/positions",
                "update_position",
                "update_position",
                self.up_pos,
            ),
            (
                "POST",
                "/api/v1/data/manual/transactions",
                "add_manual_transaction",
                "add_manual_transaction",
                self.add_manual_tx,
            ),
            (
                "PUT",
                "/api/v1/data/manual/transactions/<tx_id>",
                "update_manual_transaction",
                "update_manual_transaction",
                self.up_manual_tx,
            ),
            (
                "DELETE",
                "/api/v1/data/manual/transactions/<tx_id>",
                "delete_manual_transaction",
                "delete_manual_transaction",
                self.del_manual_tx,
            ),
            (
                "GET",
                "/api/v1/historic",
                "historic",
                "get_historic",
                self.get_historic,
            ),
            (
                "GET",
                "/api/v1/assets/instruments",
                "instruments",
                "instruments",
                self.get_instruments,
            ),
            (
                "GET",
                "/api/v1/assets/instruments/details",
                "instrument_details",
                "instrument_details",
                self.get_inst_info,
            ),
            (
                "GET",
                "/api/v1/assets/crypto",
                "search_crypto_assets",
                "search_crypto_assets",
                self.search_crypto,
            ),
            (
                "GET",
                "/api/v1/assets/crypto/<asset_id>",
                "get_crypto_asset_details",
                "get_crypto_asset_details",
                self.get_crypto_details,
            ),
            (
                "POST",
                "/api/v1/data/manual/positions/update-quotes",
                "update_tracked_quotes",
                "update_tracked_quotes",
                self.up_tracked,
            ),
            (
                "GET",
                "/api/v1/templates",
                "get_templates",
                "get_templates",
                self.get_tmpl,
            ),
            (
                "POST",
                "/api/v1/templates",
                "create_template",
                "create_template",
                self.create_tmpl,
            ),
            (
                "PUT",
                "/api/v1/templates",
                "update_template",
                "update_template",
                self.up_tmpl,
            ),
            (
                "DELETE",
                "/api/v1/templates/<template_id>",
                "delete_template",
                "delete_template",
                self.del_tmpl,
            ),
            (
                "GET",
                "/api/v1/templates/fields",
                "get_template_fields_route",
                "get_template_fields",
                self.get_tmpl_fields,
            ),
            (
                "POST",
                "/api/v1/calculations/savings",
                "calculate_savings",
                "calculate_savings",
                self.calc_savings,
            ),
            (
                "POST",
                "/api/v1/cloud/backup/upload",
                "upload_backup",
                "upload_backup",
                self.upload_backup,
            ),
            (
                "POST",
                "/api/v1/cloud/backup/import",
                "import_backup",
                "import_backup",
                self.import_backup,
            ),
            (
                "GET",
                "/api/v1/cloud/backup",
                "get_backups",
                "get_backups",
                self.get_backups,
            ),
            (
                "POST",
                "/api/v1/cloud/auth",
                "handle_cloud_auth",
                "handle_cloud_auth",
                self.handle_cloud,
            ),
            (
                "GET",
                "/api/v1/cloud/auth",
                "get_cloud_auth",
                "get_cloud_auth",
                self.get_cloud,
            ),
            (
                "GET",
                "/api/v1/cloud/backup/settings",
                "get_backup_settings",
                "get_backup_settings",
                self.get_bkp_settings,
            ),
            (
                "POST",
                "/api/v1/cloud/backup/settings",
                "save_backup_settings",
                "save_backup_settings",
                self.save_bkp_settings,
            ),
        ]

        for method, path, module_name, func_name, dep in route_map:
            r.add(method, path, bind(module_name, func_name, dep))
