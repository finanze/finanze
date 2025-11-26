import argparse
import logging
from pathlib import Path

import domain.native_entities
from application.use_cases.add_entity_credentials import AddEntityCredentialsImpl
from application.use_cases.add_manual_transaction import AddManualTransactionImpl
from application.use_cases.calculate_loan import CalculateLoanImpl
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
from application.use_cases.get_contributions import GetContributionsImpl
from application.use_cases.get_exchange_rates import GetExchangeRatesImpl
from application.use_cases.get_external_integrations import GetExternalIntegrationsImpl
from application.use_cases.get_historic import GetHistoricImpl
from application.use_cases.get_instrument_info import GetInstrumentInfoImpl
from application.use_cases.get_instruments import GetInstrumentsImpl
from application.use_cases.get_status import GetStatusImpl
from application.use_cases.get_pending_flows import GetPendingFlowsImpl
from application.use_cases.get_periodic_flows import GetPeriodicFlowsImpl
from application.use_cases.get_position import GetPositionImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.get_template_fields import GetTemplateFieldsImpl
from application.use_cases.get_templates import GetTemplatesImpl
from application.use_cases.get_transactions import GetTransactionsImpl
from application.use_cases.import_sheets import ImportSheetsImpl
from application.use_cases.import_file import ImportFileImpl
from application.use_cases.list_real_estate import ListRealEstateImpl
from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.save_commodities import SaveCommoditiesImpl
from application.use_cases.save_pending_flows import SavePendingFlowsImpl
from application.use_cases.save_periodic_flow import SavePeriodicFlowImpl
from application.use_cases.update_contributions import UpdateContributionsImpl
from application.use_cases.update_crypto_wallet import UpdateCryptoWalletConnectionImpl
from application.use_cases.update_manual_transaction import UpdateManualTransactionImpl
from application.use_cases.update_periodic_flow import UpdatePeriodicFlowImpl
from application.use_cases.update_position import UpdatePositionImpl
from application.use_cases.update_real_estate import UpdateRealEstateImpl
from application.use_cases.update_settings import UpdateSettingsImpl
from application.use_cases.update_template import UpdateTemplateImpl
from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
from application.use_cases.user_login import UserLoginImpl
from application.use_cases.user_logout import UserLogoutImpl
from domain.exception.exceptions import UserNotFound
from domain.export import FileFormat
from domain.external_integration import ExternalIntegrationId
from domain.user_login import LoginRequest
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient
from infrastructure.client.crypto.etherscan.ethplorer_client import EthplorerClient
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
from infrastructure.client.financial.gocardless.gocardless_client import (
    GoCardlessClient,
)
from infrastructure.client.instrument.instrument_provider_adapter import (
    InstrumentProviderAdapter,
)
from infrastructure.client.rates.crypto.crypto_price_client import CryptoAssetInfoClient
from infrastructure.client.rates.exchange_rate_client import ExchangeRateClient
from infrastructure.client.rates.metal.metal_price_client import MetalPriceClient
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.controller.config import flask
from infrastructure.controller.controllers import register_routes
from infrastructure.config.server_options_adapter import ArgparseServerOptionsAdapter
from infrastructure.credentials.credentials_reader import CredentialsReader
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
from waitress import serve


class FinanzeServer:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self._log = logging.getLogger(__name__)

        self._log.info("Initializing components...")

        self.db_client = DBClient()
        self.db_manager = DBManager(self.db_client)
        self.data_manager = UserDataManager(self.args.data_dir)

        static_upload_dir = self.args.data_dir / Path("static")

        self.config_loader = ConfigLoader()
        self.sheets_initiator = SheetsServiceLoader()
        self.etherscan_client = EtherscanClient()
        self.ethplorer_client = EthplorerClient()
        self.gocardless_client = GoCardlessClient(port=self.args.port)

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

        self.external_entity_fetchers = {
            ExternalIntegrationId.GOCARDLESS: GoCardlessFetcher(self.gocardless_client),
        }

        self.external_integrations = {
            ExternalIntegrationId.GOOGLE_SHEETS: self.sheets_initiator,
            ExternalIntegrationId.ETHERSCAN: self.etherscan_client,
            ExternalIntegrationId.GOCARDLESS: self.gocardless_client,
            ExternalIntegrationId.ETHPLORER: self.ethplorer_client,
        }

        self.sheets_adapter = SheetsAdapter(self.sheets_initiator)
        table_rw_adapter = TableRWDispatcher(
            {
                FileFormat.CSV: CSVFileTableAdapter(),
                FileFormat.TSV: CSVFileTableAdapter(),
                FileFormat.XLSX: XLSXFileTableAdapter(),
            }
        )

        template_processor = TemplatedDataGenerator()
        template_parser = TemplateDataParser()

        position_repository = PositionRepository(client=self.db_client)
        manual_position_data_repository = ManualPositionDataSQLRepository(
            client=self.db_client
        )
        auto_contrib_repository = AutoContributionsRepository(client=self.db_client)
        transaction_repository = TransactionRepository(client=self.db_client)
        historic_repository = HistoricRepository(client=self.db_client)
        entity_repository = EntityRepository(client=self.db_client)
        sessions_repository = SessionsRepository(client=self.db_client)
        virtual_import_registry = VirtualImportRepository(client=self.db_client)
        crypto_wallet_connections_repository = CryptoWalletConnectionRepository(
            client=self.db_client
        )
        crypto_assset_repository = CryptoAssetRegistryRepository(client=self.db_client)
        last_fetches_repository = LastFetchesRepository(client=self.db_client)
        external_integration_repository = ExternalIntegrationRepository(
            client=self.db_client
        )
        periodic_flow_repository = PeriodicFlowRepository(client=self.db_client)
        pending_flow_repository = PendingFlowRepository(client=self.db_client)
        real_estate_repository = RealEstateRepository(client=self.db_client)
        external_entity_repository = ExternalEntityRepository(client=self.db_client)
        template_repository = TemplateRepository(client=self.db_client)

        file_storage_repository = LocalFileStorage(
            upload_dir=static_upload_dir, static_url_prefix="/static"
        )
        exchange_rate_storage = ExchangeRateFileStorage(self.args.data_dir)

        exchange_rate_client = ExchangeRateClient()
        crypto_asset_info_client = CryptoAssetInfoClient()
        metal_price_client = MetalPriceClient()
        instrument_provider = InstrumentProviderAdapter()

        credentials_storage_mode = self.args.credentials_storage_mode
        if credentials_storage_mode == "DB":
            credentials_port = CredentialsRepository(client=self.db_client)
        elif credentials_storage_mode == "ENV":
            credentials_port = CredentialsReader()
        else:
            raise ValueError(
                f"Invalid credentials storage mode: {credentials_storage_mode}"
            )

        transaction_handler = TransactionHandler(client=self.db_client)

        user_login = UserLoginImpl(
            self.db_manager,
            self.data_manager,
            self.config_loader,
            self.sheets_initiator,
        )
        register_user = RegisterUserImpl(
            self.db_manager,
            self.data_manager,
            self.config_loader,
            self.sheets_initiator,
        )
        change_user_password = ChangeUserPasswordImpl(
            self.db_manager, self.data_manager
        )
        server_options_port = ArgparseServerOptionsAdapter(self.args)
        get_status = GetStatusImpl(
            self.db_manager,
            self.data_manager,
            server_options_port,
        )
        user_logout = UserLogoutImpl(
            self.db_manager, self.config_loader, self.sheets_initiator
        )

        get_available_entities = GetAvailableEntitiesImpl(
            entity_repository,
            external_entity_repository,
            credentials_port,
            crypto_wallet_connections_repository,
            last_fetches_repository,
            virtual_import_registry,
        )
        fetch_financial_data = FetchFinancialDataImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            self.financial_entity_fetchers,
            self.config_loader,
            credentials_port,
            sessions_repository,
            last_fetches_repository,
            transaction_handler,
        )
        fetch_crypto_data = FetchCryptoDataImpl(
            position_repository,
            self.crypto_entity_fetchers,
            crypto_wallet_connections_repository,
            crypto_assset_repository,
            crypto_asset_info_client,
            last_fetches_repository,
            external_integration_repository,
            transaction_handler,
        )
        fetch_external_financial_data = FetchExternalFinancialDataImpl(
            entity_repository,
            external_entity_repository,
            position_repository,
            self.external_entity_fetchers,
            external_integration_repository,
            last_fetches_repository,
            transaction_handler,
        )
        export_sheets = ExportSheetsImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            self.sheets_adapter,
            last_fetches_repository,
            external_integration_repository,
            entity_repository,
            template_repository,
            template_processor,
            self.config_loader,
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
            self.sheets_adapter,
            entity_repository,
            external_integration_repository,
            self.config_loader,
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
            self.financial_entity_fetchers,
            credentials_port,
            sessions_repository,
            transaction_handler,
        )
        disconnect_entity = DisconnectEntityImpl(
            credentials_port, sessions_repository, transaction_handler
        )
        get_settings = GetSettingsImpl(self.config_loader)
        update_settings = UpdateSettingsImpl(self.config_loader)
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
            self.external_entity_fetchers,
            external_integration_repository,
            file_storage_repository,
        )
        complete_external_entity_connection = CompleteExternalEntityConnectionImpl(
            external_entity_repository,
            self.external_entity_fetchers,
            external_integration_repository,
        )
        delete_external_entity = DeleteExternalEntityImpl(
            external_entity_repository,
            self.external_entity_fetchers,
            external_integration_repository,
        )
        get_available_external_entities = GetAvailableExternalEntitiesImpl(
            entity_repository,
            external_entity_repository,
            self.external_entity_fetchers,
            external_integration_repository,
        )
        connect_crypto_wallet = ConnectCryptoWalletImpl(
            crypto_wallet_connections_repository,
            self.crypto_entity_fetchers,
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
            external_integration_repository
        )
        connect_external_integrations = ConnectExternalIntegrationImpl(
            external_integration_repository,
            self.external_integrations,
        )
        disconnect_external_integrations = DisconnectExternalIntegrationImpl(
            external_integration_repository
        )

        get_instruments = GetInstrumentsImpl(instrument_provider)
        get_instrument_info = GetInstrumentInfoImpl(instrument_provider)

        save_periodic_flow = SavePeriodicFlowImpl(periodic_flow_repository)
        update_periodic_flow = UpdatePeriodicFlowImpl(periodic_flow_repository)
        delete_periodic_flow = DeletePeriodicFlowImpl(periodic_flow_repository)
        get_periodic_flows = GetPeriodicFlowsImpl(periodic_flow_repository)
        save_pending_flows = SavePendingFlowsImpl(
            pending_flow_repository, transaction_handler
        )
        get_pending_flows = GetPendingFlowsImpl(pending_flow_repository)

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

        self._log.info("Initial component setup completed.")

        self._init_user(args, user_login)

        self._log.info("Setting up REST API...")

        self.flask_app = flask(static_upload_dir)
        register_routes(
            self.flask_app,
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
            forecast,
            update_contributions,
            update_position,
            add_manual_transaction,
            update_manual_transaction,
            delete_manual_transaction,
            get_instruments,
            get_instrument_info,
            update_tracked_quotes,
            create_template,
            update_template,
            delete_template,
            get_templates,
            get_template_fields,
        )

        self._log.info("Warming up exchange rates...")
        get_exchange_rates.execute(initial_load=True)

        self._log.info("Completed.")

    def _init_user(self, args, user_login: UserLoginImpl):
        if args.logged_username and args.logged_password:
            self._log.info("User provided, logging in...")
            try:
                user_login.execute(
                    LoginRequest(args.logged_username, args.logged_password)
                )
            except UserNotFound:
                self._log.warning(
                    f"User {args.logged_username} not found during login."
                )

    def run(self):
        self._log.info(f"Starting Finanze server on port {self.args.port}...")
        try:
            serve(self.flask_app, host="0.0.0.0", port=self.args.port)
        except OSError as e:
            self._log.error(f"Could not start server on port {self.args.port}: {e}")
            if e.errno == 48:
                self._log.info(f"Port {self.args.port} is already in use.")
            else:
                raise
        except Exception:
            self._log.exception(
                "An unexpected error occurred while running the server."
            )
            raise
        finally:
            self._log.info("Finanze server shutting down.")
            if self.db_client and self.db_client.silent_close():
                self._log.info("Database connection closed.")
