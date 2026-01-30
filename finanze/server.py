import argparse
import logging
import os
import socket
from pathlib import Path

import uvicorn

import domain.native_entities
from application.use_cases.add_entity_credentials import AddEntityCredentialsImpl
from application.use_cases.add_manual_transaction import AddManualTransactionImpl
from application.use_cases.calculate_loan import CalculateLoanImpl
from application.use_cases.calculate_savings import CalculateSavingsImpl
from application.use_cases.change_user_password import ChangeUserPasswordImpl
from application.use_cases.complete_external_entity_connection import (
    CompleteExternalEntityConnectionImpl,
)
from application.use_cases.connect_crypto_wallet import ConnectCryptoWalletImpl
from application.use_cases.connect_external_entity import ConnectExternalEntityImpl
from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.create_real_estate import CreateRealEstateImpl
from application.use_cases.create_template import CreateTemplateImpl
from application.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnectionImpl
from application.use_cases.delete_external_entity import DeleteExternalEntityImpl
from application.use_cases.delete_manual_transaction import DeleteManualTransactionImpl
from application.use_cases.delete_periodic_flow import DeletePeriodicFlowImpl
from application.use_cases.delete_real_estate import DeleteRealEstateImpl
from application.use_cases.delete_template import DeleteTemplateImpl
from application.use_cases.disconnect_entity import DisconnectEntityImpl
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.export_file import ExportFileImpl
from application.use_cases.export_sheets import ExportSheetsImpl
from application.use_cases.fetch_crypto_data import FetchCryptoDataImpl
from application.use_cases.fetch_external_financial_data import (
    FetchExternalFinancialDataImpl,
)
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from application.use_cases.forecast import ForecastImpl
from application.use_cases.get_available_entities import GetAvailableEntitiesImpl
from application.use_cases.get_available_external_entities import (
    GetAvailableExternalEntitiesImpl,
)
from application.use_cases.get_backup_settings import GetBackupSettingsImpl
from application.use_cases.get_backups import GetBackupsImpl
from application.use_cases.get_cloud_auth import GetCloudAuthImpl
from application.use_cases.get_contributions import GetContributionsImpl
from application.use_cases.get_crypto_asset_details import GetCryptoAssetDetailsImpl
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
from application.use_cases.import_sheets import ImportSheetsImpl
from application.use_cases.list_real_estate import ListRealEstateImpl
from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.save_backup_settings import SaveBackupSettingsImpl
from application.use_cases.save_commodities import SaveCommoditiesImpl
from application.use_cases.save_pending_flows import SavePendingFlowsImpl
from application.use_cases.save_periodic_flow import SavePeriodicFlowImpl
from application.use_cases.search_crypto_assets import SearchCryptoAssetsImpl
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
from domain.backup import BackupFileType
from domain.export import FileFormat
from domain.external_integration import ExternalIntegrationId
from domain.user_login import LoginRequest
from infrastructure.client.cloud.backup.backup_client import BackupClient
from infrastructure.client.cloud.backup.http_file_transfer_strategy import (
    HttpFileTransferStrategy,
)
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
from infrastructure.client.entity.financial.ing.ing_fetcher import INGFetcher
from infrastructure.client.entity.financial.mintos.mintos_fetcher import MintosFetcher
from infrastructure.client.entity.financial.myinvestor import MyInvestorScraper
from infrastructure.client.entity.financial.psd2.gocardless_fetcher import (
    GoCardlessFetcher,
)
from infrastructure.client.entity.financial.sego.sego_fetcher import SegoFetcher
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    TradeRepublicFetcher,
)
from infrastructure.client.entity.financial.unicaja.unicaja_fetcher import (
    UnicajaFetcher,
)
from infrastructure.client.entity.financial.urbanitae.urbanitae_fetcher import (
    UrbanitaeFetcher,
)
from infrastructure.client.entity.financial.wecity.wecity_fetcher import WecityFetcher
from infrastructure.client.features.feature_flag_client import FeatureFlagClient
from infrastructure.client.financial.gocardless.gocardless_client import (
    GoCardlessClient,
)
from infrastructure.client.instrument.instrument_provider_adapter import (
    InstrumentProviderAdapter,
)
from infrastructure.client.rates.crypto.crypto_price_client import CryptoAssetInfoClient
from infrastructure.client.rates.crypto.file_coingecko_strategy import (
    FileCoinGeckoCacheStrategy,
)
from infrastructure.client.rates.exchange_rate_client import ExchangeRateClient
from infrastructure.client.rates.metal.metal_price_client import MetalPriceClient
from infrastructure.cloud.backup.backup_processor_adapter import (
    BackupProcessorAdapter,
)
from infrastructure.cloud.cloud_data_register import CloudDataRegister
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.config.server_details_adapter import ServerDetailsAdapter
from infrastructure.controller.config import quart
from infrastructure.controller.controllers import register_routes
from infrastructure.credentials.credentials_reader import CredentialsReader
from infrastructure.features.env_feature_flag_adapter import EnvFeatureFlagAdapter
from infrastructure.file_storage.exchange_rate_file_storage import (
    ExchangeRateFileStorage,
)
from infrastructure.file_storage.local_file_storage import LocalFileStorage
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
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
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
from infrastructure.sheets.sheets_adapter import SheetsAdapter
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader
from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
from infrastructure.templating.templated_data_generator import TemplatedDataGenerator
from infrastructure.templating.templated_data_parser import TemplateDataParser
from infrastructure.user_files.user_data_manager import UserDataManager


class FinanzeServer:
    def __init__(self, args: argparse.Namespace):
        self._args = args
        self._quart_app = None
        self._db_client = None
        self._log = logging.getLogger(__name__)

    async def _init(self):
        args = self._args
        self._check_port()

        self._log.info("Initializing components...")

        self._db_client = DBClient()
        db_client = self._db_client
        db_manager = DBManager(db_client)
        data_manager = UserDataManager(args.data_dir)

        static_upload_dir = args.data_dir / Path("static")

        config_loader = ConfigLoader()
        sheets_initiator = SheetsServiceLoader()
        cloud_register = CloudDataRegister()
        etherscan_client = EtherscanClient()
        ethplorer_client = EthplorerClient()
        gocardless_client = GoCardlessClient(port=args.port)

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
            domain.native_entities.UNICAJA: UnicajaFetcher(),
            domain.native_entities.URBANITAE: UrbanitaeFetcher(),
            domain.native_entities.WECITY: WecityFetcher(),
            domain.native_entities.SEGO: SegoFetcher(),
            domain.native_entities.MINTOS: MintosFetcher(),
            domain.native_entities.F24: F24Fetcher(),
            domain.native_entities.INDEXA_CAPITAL: IndexaCapitalFetcher(),
            domain.native_entities.ING: INGFetcher(),
            domain.native_entities.CAJAMAR: CajamarFetcher(),
        }

        external_entity_fetchers = {
            ExternalIntegrationId.GOCARDLESS: GoCardlessFetcher(gocardless_client),
        }

        external_integrations = {
            ExternalIntegrationId.GOOGLE_SHEETS: sheets_initiator,
            ExternalIntegrationId.ETHERSCAN: etherscan_client,
            ExternalIntegrationId.GOCARDLESS: gocardless_client,
            ExternalIntegrationId.ETHPLORER: ethplorer_client,
        }

        sheets_adapter = SheetsAdapter(sheets_initiator)
        csv_tsv_adapter = CSVFileTableAdapter()
        table_rw_adapter = TableRWDispatcher(
            {
                FileFormat.CSV: csv_tsv_adapter,
                FileFormat.TSV: csv_tsv_adapter,
                FileFormat.XLSX: XLSXFileTableAdapter(),
            }
        )

        template_processor = TemplatedDataGenerator()
        template_parser = TemplateDataParser()

        position_repository = PositionRepository(client=db_client)
        manual_position_data_repository = ManualPositionDataSQLRepository(
            client=db_client
        )
        auto_contrib_repository = AutoContributionsRepository(client=db_client)
        transaction_repository = TransactionRepository(client=db_client)
        historic_repository = HistoricRepository(client=db_client)
        entity_repository = EntityRepository(client=db_client)
        sessions_repository = SessionsRepository(client=db_client)
        virtual_import_registry = VirtualImportRepository(client=db_client)
        crypto_wallet_connections_repository = CryptoWalletConnectionRepository(
            client=db_client
        )
        crypto_asset_repository = CryptoAssetRegistryRepository(client=db_client)
        last_fetches_repository = LastFetchesRepository(client=db_client)
        external_integration_repository = ExternalIntegrationRepository(
            client=db_client
        )
        periodic_flow_repository = PeriodicFlowRepository(client=db_client)
        pending_flow_repository = PendingFlowRepository(client=db_client)
        real_estate_repository = RealEstateRepository(client=db_client)
        external_entity_repository = ExternalEntityRepository(client=db_client)
        template_repository = TemplateRepository(client=db_client)

        file_storage_repository = LocalFileStorage(
            upload_dir=static_upload_dir, static_url_prefix="/static"
        )
        exchange_rate_storage = ExchangeRateFileStorage(args.data_dir)

        exchange_rate_client = ExchangeRateClient()
        crypto_asset_info_client = CryptoAssetInfoClient(
            coingecko_strategy=FileCoinGeckoCacheStrategy(str(args.data_dir))
        )
        metal_price_client = MetalPriceClient()
        instrument_provider = InstrumentProviderAdapter()

        credentials_storage_mode = args.credentials_storage_mode
        if credentials_storage_mode == "DB":
            credentials_port = CredentialsRepository(client=db_client)
        elif credentials_storage_mode == "ENV":
            credentials_port = CredentialsReader()
        else:
            raise ValueError(
                f"Invalid credentials storage mode: {credentials_storage_mode}"
            )

        transaction_handler = TransactionHandler(client=db_client)

        user_login = UserLoginImpl(
            db_manager,
            data_manager,
            config_loader,
            sheets_initiator,
            cloud_register,
        )
        register_user = RegisterUserImpl(
            db_manager,
            data_manager,
            config_loader,
            sheets_initiator,
            cloud_register,
        )
        change_user_password = ChangeUserPasswordImpl(db_manager, data_manager)
        server_options_port = ServerDetailsAdapter(args)
        if os.getenv("ENV_FF"):
            feature_flag_port = EnvFeatureFlagAdapter()
        else:
            users = await data_manager.get_users()
            feature_flag_port = FeatureFlagClient(
                operative_system=server_options_port.get_os(), users=users
            )
            await feature_flag_port.load()

        get_status = GetStatusImpl(
            db_manager,
            data_manager,
            server_options_port,
            feature_flag_port,
        )
        user_logout = UserLogoutImpl(
            db_manager,
            config_loader,
            sheets_initiator,
            cloud_register,
        )

        get_available_entities = GetAvailableEntitiesImpl(
            entity_repository,
            external_entity_repository,
            credentials_port,
            crypto_wallet_connections_repository,
            last_fetches_repository,
            virtual_import_registry,
            financial_entity_fetchers,
            external_entity_fetchers,
        )
        fetch_financial_data = FetchFinancialDataImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            financial_entity_fetchers,
            config_loader,
            credentials_port,
            sessions_repository,
            last_fetches_repository,
            crypto_asset_repository,
            crypto_asset_info_client,
            transaction_handler,
        )
        fetch_crypto_data = FetchCryptoDataImpl(
            position_repository,
            crypto_entity_fetchers,
            crypto_wallet_connections_repository,
            crypto_asset_repository,
            crypto_asset_info_client,
            last_fetches_repository,
            external_integration_repository,
            transaction_handler,
        )
        fetch_external_financial_data = FetchExternalFinancialDataImpl(
            entity_repository,
            external_entity_repository,
            position_repository,
            external_entity_fetchers,
            external_integration_repository,
            last_fetches_repository,
            transaction_handler,
        )
        export_sheets = ExportSheetsImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            sheets_adapter,
            last_fetches_repository,
            external_integration_repository,
            entity_repository,
            template_repository,
            template_processor,
            config_loader,
        )
        export_file = ExportFileImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            entity_repository,
            template_repository,
            template_processor,
            table_rw_adapter,
        )
        import_sheets = ImportSheetsImpl(
            position_repository,
            transaction_repository,
            sheets_adapter,
            entity_repository,
            external_integration_repository,
            config_loader,
            virtual_import_registry,
            template_repository,
            template_parser,
            transaction_handler,
        )
        import_file = ImportFileImpl(
            position_port=position_repository,
            transaction_port=transaction_repository,
            table_rw_port=table_rw_adapter,
            entity_port=entity_repository,
            virtual_import_registry=virtual_import_registry,
            template_port=template_repository,
            template_parser=template_parser,
            transaction_handler_port=transaction_handler,
        )
        add_entity_credentials = AddEntityCredentialsImpl(
            financial_entity_fetchers,
            credentials_port,
            sessions_repository,
            transaction_handler,
        )
        disconnect_entity = DisconnectEntityImpl(
            credentials_port, sessions_repository, transaction_handler
        )
        get_settings = GetSettingsImpl(config_loader)
        update_settings = UpdateSettingsImpl(config_loader)
        get_entities_position = GetPositionImpl(position_repository, entity_repository)
        get_contributions = GetContributionsImpl(
            auto_contrib_repository, entity_repository
        )
        get_historic = GetHistoricImpl(historic_repository, entity_repository)
        get_transactions = GetTransactionsImpl(
            transaction_repository, entity_repository
        )
        get_exchange_rates = GetExchangeRatesImpl(
            exchange_rate_client,
            crypto_asset_info_client,
            metal_price_client,
            exchange_rate_storage,
            position_repository,
        )
        connect_external_entity = ConnectExternalEntityImpl(
            entity_repository,
            external_entity_repository,
            external_entity_fetchers,
            external_integration_repository,
        )
        complete_external_entity_connection = CompleteExternalEntityConnectionImpl(
            external_entity_repository,
            external_entity_fetchers,
            external_integration_repository,
        )
        delete_external_entity = DeleteExternalEntityImpl(
            external_entity_repository,
            external_entity_fetchers,
            external_integration_repository,
        )
        get_available_external_entities = GetAvailableExternalEntitiesImpl(
            entity_repository,
            external_entity_repository,
            external_entity_fetchers,
            external_integration_repository,
        )
        connect_crypto_wallet = ConnectCryptoWalletImpl(
            crypto_wallet_connections_repository,
            crypto_entity_fetchers,
            external_integration_repository,
        )
        update_crypto_wallet = UpdateCryptoWalletConnectionImpl(
            crypto_wallet_connections_repository
        )
        delete_crypto_wallet = DeleteCryptoWalletConnectionImpl(
            crypto_wallet_connections_repository
        )
        save_commodities = SaveCommoditiesImpl(
            position_repository,
            exchange_rate_client,
            metal_price_client,
            last_fetches_repository,
            transaction_handler,
        )
        get_external_integrations = GetExternalIntegrationsImpl(
            external_integration_repository, external_integrations
        )
        connect_external_integrations = ConnectExternalIntegrationImpl(
            external_integration_repository,
            external_integrations,
        )
        disconnect_external_integrations = DisconnectExternalIntegrationImpl(
            external_integration_repository
        )

        get_instruments = GetInstrumentsImpl(instrument_provider)
        get_instrument_info = GetInstrumentInfoImpl(instrument_provider)
        search_crypto_assets = SearchCryptoAssetsImpl(crypto_asset_info_client)
        get_crypto_asset_details = GetCryptoAssetDetailsImpl(
            crypto_asset_info_client, entity_repository
        )

        save_periodic_flow = SavePeriodicFlowImpl(periodic_flow_repository)
        update_periodic_flow = UpdatePeriodicFlowImpl(periodic_flow_repository)
        delete_periodic_flow = DeletePeriodicFlowImpl(periodic_flow_repository)
        get_periodic_flows = GetPeriodicFlowsImpl(periodic_flow_repository)
        save_pending_flows = SavePendingFlowsImpl(
            pending_flow_repository, transaction_handler
        )
        get_pending_flows = GetPendingFlowsImpl(pending_flow_repository)
        get_money_events = GetMoneyEventsImpl(
            get_contributions,
            get_periodic_flows,
            get_pending_flows,
            entity_repository,
            position_repository,
        )

        create_real_estate = CreateRealEstateImpl(
            real_estate_repository,
            periodic_flow_repository,
            transaction_handler,
            file_storage_repository,
        )
        update_real_estate = UpdateRealEstateImpl(
            real_estate_repository,
            periodic_flow_repository,
            transaction_handler,
            file_storage_repository,
        )
        delete_real_estate = DeleteRealEstateImpl(
            real_estate_repository,
            periodic_flow_repository,
            transaction_handler,
            file_storage_repository,
        )
        list_real_estate = ListRealEstateImpl(real_estate_repository)
        calculate_loan = CalculateLoanImpl()
        calculate_savings = CalculateSavingsImpl()
        forecast = ForecastImpl(
            position_port=position_repository,
            auto_contributions_port=auto_contrib_repository,
            periodic_flow_port=periodic_flow_repository,
            pending_flow_port=pending_flow_repository,
            real_estate_port=real_estate_repository,
            entity_port=entity_repository,
        )
        update_contributions = UpdateContributionsImpl(
            entity_port=entity_repository,
            auto_contributions_port=auto_contrib_repository,
            virtual_import_registry=virtual_import_registry,
            transaction_handler_port=transaction_handler,
        )
        update_position = UpdatePositionImpl(
            entity_port=entity_repository,
            position_port=position_repository,
            manual_position_data_port=manual_position_data_repository,
            virtual_import_registry=virtual_import_registry,
            crypto_asset_registry_port=crypto_asset_repository,
            crypto_asset_info_provider=crypto_asset_info_client,
            transaction_handler_port=transaction_handler,
        )
        add_manual_transaction = AddManualTransactionImpl(
            entity_port=entity_repository,
            transaction_port=transaction_repository,
            virtual_import_registry=virtual_import_registry,
            transaction_handler_port=transaction_handler,
        )
        update_manual_transaction = UpdateManualTransactionImpl(
            entity_port=entity_repository,
            transaction_port=transaction_repository,
            virtual_import_registry=virtual_import_registry,
            transaction_handler_port=transaction_handler,
        )
        delete_manual_transaction = DeleteManualTransactionImpl(
            transaction_port=transaction_repository,
            virtual_import_registry=virtual_import_registry,
            transaction_handler_port=transaction_handler,
        )
        update_tracked_quotes = UpdateTrackedQuotesImpl(
            position_port=position_repository,
            manual_position_data_port=manual_position_data_repository,
            instrument_info_provider=instrument_provider,
            exchange_rate_provider=exchange_rate_client,
        )
        create_template = CreateTemplateImpl(template_repository)
        update_template = UpdateTemplateImpl(template_repository)
        delete_template = DeleteTemplateImpl(template_repository)
        get_templates = GetTemplatesImpl(template_repository)
        get_template_fields = GetTemplateFieldsImpl()

        backup_processor = BackupProcessorAdapter()
        backup_repository = BackupClient(HttpFileTransferStrategy())

        backupable_ports = {
            BackupFileType.DATA: db_manager,
            BackupFileType.CONFIG: config_loader,
        }
        upload_backup = UploadBackupImpl(
            data_initiator=db_manager,
            backupable_ports=backupable_ports,
            backup_processor=backup_processor,
            backup_repository=backup_repository,
            backup_local_registry=cloud_register,
            cloud_register=cloud_register,
        )
        import_backup = ImportBackupImpl(
            data_initiator=db_manager,
            backupable_ports=backupable_ports,
            backup_processor=backup_processor,
            backup_repository=backup_repository,
            backup_local_registry=cloud_register,
            cloud_register=cloud_register,
        )
        get_backups = GetBackupsImpl(
            backupable_ports=backupable_ports,
            backup_repository=backup_repository,
            backup_local_registry=cloud_register,
            cloud_register=cloud_register,
        )

        handle_cloud_auth = HandleCloudAuthImpl(
            cloud_register=cloud_register,
        )

        get_cloud_auth = GetCloudAuthImpl(
            cloud_register=cloud_register,
        )

        get_backup_settings = GetBackupSettingsImpl(
            backup_settings_port=cloud_register,
        )

        save_backup_settings = SaveBackupSettingsImpl(
            backup_settings_port=cloud_register,
        )

        self._log.info("Initial component setup completed.")

        await self._init_user(args, user_login)

        self._log.info("Setting up REST API...")

        self._quart_app = quart(static_upload_dir)
        await register_routes(
            self._quart_app,
            user_login,
            register_user,
            change_user_password,
            get_available_entities,
            fetch_financial_data,
            fetch_crypto_data,
            fetch_external_financial_data,
            export_sheets,
            export_file,
            import_sheets,
            import_file,
            add_entity_credentials,
            get_status,
            user_logout,
            get_settings,
            update_settings,
            disconnect_entity,
            get_entities_position,
            get_contributions,
            get_historic,
            get_transactions,
            get_exchange_rates,
            get_money_events,
            connect_external_entity,
            complete_external_entity_connection,
            delete_external_entity,
            get_available_external_entities,
            connect_crypto_wallet,
            update_crypto_wallet,
            delete_crypto_wallet,
            save_commodities,
            get_external_integrations,
            connect_external_integrations,
            disconnect_external_integrations,
            save_periodic_flow,
            update_periodic_flow,
            delete_periodic_flow,
            get_periodic_flows,
            save_pending_flows,
            get_pending_flows,
            create_real_estate,
            update_real_estate,
            delete_real_estate,
            list_real_estate,
            calculate_loan,
            calculate_savings,
            forecast,
            update_contributions,
            update_position,
            add_manual_transaction,
            update_manual_transaction,
            delete_manual_transaction,
            get_instruments,
            get_instrument_info,
            update_tracked_quotes,
            search_crypto_assets,
            get_crypto_asset_details,
            create_template,
            update_template,
            delete_template,
            get_templates,
            get_template_fields,
            upload_backup,
            import_backup,
            get_backups,
            handle_cloud_auth,
            get_cloud_auth,
            get_backup_settings,
            save_backup_settings,
        )

        self._log.info("Warming up exchange rates...")
        await get_exchange_rates.execute(initial_load=True)

        self._log.info("Completed.")

    async def _init_user(self, args, user_login: UserLoginImpl):
        if args.logged_username and args.logged_password:
            self._log.info("User provided, logging in...")
            try:
                await user_login.execute(
                    LoginRequest(args.logged_username, args.logged_password)
                )
            except Exception as e:
                self._log.error(f"Failed to login user: {e}")
                raise

    async def run(self):
        self._log.info(f"Initializing Finanze server on port {self._args.port}...")
        try:
            await self._init()
        except OSError as e:
            if "Port" in str(e):
                self._log.error(f"Initialization failed: {e}")
                return
            else:
                raise

        self._log.info("Starting server...")

        config = uvicorn.Config(
            self._quart_app,
            host="0.0.0.0",
            port=self._args.port,
            log_config=None,
            log_level=None,
            access_log=True,
        )
        server = uvicorn.Server(config)

        try:
            await server.serve()
        except OSError as e:
            self._log.error(f"Could not start server on port {self._args.port}: {e}")
            if e.errno == 48:
                self._log.info(f"Port {self._args.port} is already in use.")
            else:
                raise
        except Exception:
            self._log.exception(
                "An unexpected error occurred while running the server."
            )
            raise
        finally:
            self._log.info("Finanze server shutting down.")
            if self._db_client and await self._db_client.silent_close():
                self._log.info("Database connection closed.")

    def _check_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            used = s.connect_ex(("localhost", self._args.port)) == 0
            if used:
                raise OSError(f"Port {self._args.port} is already in use.")
