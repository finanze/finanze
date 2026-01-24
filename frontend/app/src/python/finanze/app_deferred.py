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
        from domain.export import FileFormat
        from domain.external_integration import ExternalIntegrationId
        from infrastructure.cloud.capacitor_cloud_data_register import (
            CapacitorCloudDataRegister,
        )
        from infrastructure.config.capacitor_config_adapter import (
            CapacitorConfigAdapter,
        )
        from infrastructure.file_storage.mobile_file_storage import MobileFileStorage
        from infrastructure.file_storage.preference_exchange_storage import (
            PreferenceExchangeRateStorage,
        )
        from infrastructure.sheets.capacitor_sheets_initiator import (
            CapacitorSheetsInitiator,
        )
        from infrastructure.client.rates.crypto.preference_coingecko_strategy import (
            PreferenceCoinGeckoCacheStrategy,
        )
        from infrastructure.client.crypto.etherscan.etherscan_client import (
            EtherscanClient,
        )
        from infrastructure.client.crypto.ethplorer.ethplorer_client import (
            EthplorerClient,
        )
        from infrastructure.client.entity.crypto.bitcoin.bitcoin_fetcher import (
            BitcoinFetcher,
        )
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
        from infrastructure.client.entity.financial.wecity.wecity_fetcher import (
            WecityFetcher,
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
        from infrastructure.cloud.backup.capacitor_backup_processor import (
            CapacitorBackupProcessorAdapter,
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
        from infrastructure.repository.historic.historic_repository import (
            HistoricSQLRepository as HistoricRepository,
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
        from infrastructure.repository.sessions.sessions_repository import (
            SessionsRepository,
        )
        from infrastructure.repository.templates.template_repository import (
            TemplateRepository,
        )
        from infrastructure.repository.virtual.virtual_import_repository import (
            VirtualImportRepository,
        )
        from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
        from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
        from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
        from infrastructure.templating.templated_data_generator import (
            TemplatedDataGenerator,
        )
        from infrastructure.templating.templated_data_parser import TemplateDataParser
        from infrastructure.client.http.httpx_patch import apply_httpx_patch
        from application.use_cases.add_entity_credentials import (
            AddEntityCredentialsImpl,
        )
        from application.use_cases.add_manual_transaction import (
            AddManualTransactionImpl,
        )
        from application.use_cases.calculate_loan import CalculateLoanImpl
        from application.use_cases.calculate_savings import CalculateSavingsImpl
        from application.use_cases.connect_crypto_wallet import ConnectCryptoWalletImpl
        from application.use_cases.connect_external_integration import (
            ConnectExternalIntegrationImpl,
        )
        from application.use_cases.create_real_estate import CreateRealEstateImpl
        from application.use_cases.create_template import CreateTemplateImpl
        from application.use_cases.delete_crypto_wallet import (
            DeleteCryptoWalletConnectionImpl,
        )
        from application.use_cases.delete_manual_transaction import (
            DeleteManualTransactionImpl,
        )
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
        from application.use_cases.get_historic import GetHistoricImpl
        from application.use_cases.get_instrument_info import GetInstrumentInfoImpl
        from application.use_cases.get_instruments import GetInstrumentsImpl
        from application.use_cases.get_money_events import GetMoneyEventsImpl
        from application.use_cases.get_pending_flows import GetPendingFlowsImpl
        from application.use_cases.get_periodic_flows import GetPeriodicFlowsImpl
        from application.use_cases.get_position import GetPositionImpl
        from application.use_cases.get_template_fields import GetTemplateFieldsImpl
        from application.use_cases.get_templates import GetTemplatesImpl
        from application.use_cases.get_transactions import GetTransactionsImpl
        from application.use_cases.get_settings import GetSettingsImpl
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
        from application.use_cases.user_login import UserLoginImpl
        from application.use_cases.get_crypto_asset_details import (
            GetCryptoAssetDetailsImpl,
        )
        from application.use_cases.change_user_password import ChangeUserPasswordImpl
        from application.use_cases.update_settings import UpdateSettingsImpl
        from application.use_cases.user_logout import UserLogoutImpl
        from application.use_cases.update_contributions import UpdateContributionsImpl
        from application.use_cases.update_crypto_wallet import (
            UpdateCryptoWalletConnectionImpl,
        )
        from application.use_cases.update_manual_transaction import (
            UpdateManualTransactionImpl,
        )
        from application.use_cases.update_periodic_flow import UpdatePeriodicFlowImpl
        from application.use_cases.update_position import UpdatePositionImpl
        from application.use_cases.update_real_estate import UpdateRealEstateImpl
        from application.use_cases.update_template import UpdateTemplateImpl
        from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
        from application.use_cases.upload_backup import UploadBackupImpl

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
        self.update_settings = UpdateSettingsImpl(self.config_loader)

        etherscan_client = EtherscanClient()
        ethplorer_client = EthplorerClient()

        crypto_entity_fetchers = {
            domain.native_entities.BITCOIN: BitcoinFetcher(),
            domain.native_entities.ETHEREUM: EthereumFetcher(
                etherscan_client, ethplorer_client
            ),
            domain.native_entities.LITECOIN: LitecoinFetcher(),
            domain.native_entities.TRON: TronFetcher(),
            domain.native_entities.BSC: BSCFetcher(etherscan_client, ethplorer_client),
        }
        financial_entity_fetchers = {
            domain.native_entities.MY_INVESTOR: MyInvestorScraper(),
            domain.native_entities.TRADE_REPUBLIC: TradeRepublicFetcher(),
            domain.native_entities.URBANITAE: UrbanitaeFetcher(),
            domain.native_entities.WECITY: WecityFetcher(),
            domain.native_entities.SEGO: SegoFetcher(),
            domain.native_entities.F24: F24Fetcher(),
            domain.native_entities.INDEXA_CAPITAL: IndexaCapitalFetcher(),
            domain.native_entities.CAJAMAR: CajamarFetcher(),
        }
        external_integrations = {
            ExternalIntegrationId.ETHERSCAN: etherscan_client,
            ExternalIntegrationId.ETHPLORER: ethplorer_client,
        }

        csv_tsv_adapter = CSVFileTableAdapter()
        table_rw_adapter = TableRWDispatcher(
            {
                FileFormat.CSV: csv_tsv_adapter,
                FileFormat.TSV: csv_tsv_adapter,
                FileFormat.XLSX: XLSXFileTableAdapter(),
            }
        )

        position_repo = PositionRepository(client=db_client)
        manual_repo = ManualPositionDataSQLRepository(client=db_client)
        auto_repo = AutoContributionsRepository(client=db_client)
        tx_repo = TransactionRepository(client=db_client)
        historic_repo = HistoricRepository(client=db_client)
        entity_repo = EntityRepository(client=db_client)
        sessions_repo = SessionsRepository(client=db_client)
        virtual_repo = VirtualImportRepository(client=db_client)
        wallet_repo = CryptoWalletConnectionRepository(client=db_client)
        crypto_asset_repo = CryptoAssetRegistryRepository(client=db_client)
        last_fetches_repo = LastFetchesRepository(client=db_client)
        ext_int_repo = ExternalIntegrationRepository(client=db_client)
        period_repo = PeriodicFlowRepository(client=db_client)
        pending_repo = PendingFlowRepository(client=db_client)
        re_repo = RealEstateRepository(client=db_client)
        ext_ent_repo = ExternalEntityRepository(client=db_client)
        temp_repo = TemplateRepository(client=db_client)
        creds_repo = CredentialsRepository(client=db_client)

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

        tx_handler = TransactionHandler(client=db_client)

        template_gen = TemplatedDataGenerator()
        template_parser = TemplateDataParser()

        backup_processor = CapacitorBackupProcessorAdapter()
        file_transfer_strategy = CapacitorFileTransferStrategy()
        backup_repository = BackupClient(file_transfer_strategy)

        self.get_avail_sources = GetAvailableEntitiesImpl(
            entity_repo,
            ext_ent_repo,
            creds_repo,
            wallet_repo,
            last_fetches_repo,
            virtual_repo,
            financial_entity_fetchers,
            {},
        )
        self.add_entity_creds = AddEntityCredentialsImpl(
            financial_entity_fetchers, creds_repo, sessions_repo, tx_handler
        )
        self.disconnect_entity = DisconnectEntityImpl(
            creds_repo, sessions_repo, tx_handler
        )

        self.fetch_financial = FetchFinancialDataImpl(
            position_repo,
            auto_repo,
            tx_repo,
            historic_repo,
            financial_entity_fetchers,
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
            crypto_entity_fetchers,
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
            wallet_repo, crypto_entity_fetchers, ext_int_repo
        )
        self.up_crypto = UpdateCryptoWalletConnectionImpl(wallet_repo)
        self.del_crypto = DeleteCryptoWalletConnectionImpl(wallet_repo)

        self.save_commodities = SaveCommoditiesImpl(
            position_repo, ex_client, metal_client, last_fetches_repo, tx_handler
        )

        self.get_integrations = GetExternalIntegrationsImpl(ext_int_repo)
        self.conn_integration = ConnectExternalIntegrationImpl(
            ext_int_repo, external_integrations
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
            BackupFileType.DATA: core.db_manager,
            BackupFileType.CONFIG: self.config_loader,
        }
        self.upload_backup = UploadBackupImpl(
            core.db_manager,
            backupable_ports,
            backup_processor,
            backup_repository,
            self.cloud_register,
            self.cloud_register,
        )
        self.import_backup = ImportBackupImpl(
            core.db_manager,
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

        await ex_storage.initialize()
        await crypto_info.initialize()
