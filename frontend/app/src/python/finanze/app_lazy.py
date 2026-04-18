from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finanze.app_core import MobileAppCore
    from finanze.app_deferred import DeferredComponents


class LazyComponents:
    def __init__(self, core: "MobileAppCore", deferred: "DeferredComponents"):
        self._core = core
        self._deferred = deferred

    async def initialize(self):
        import domain.native_entities
        from domain.export import FileFormat
        from domain.external_integration import ExternalIntegrationId
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
        from infrastructure.client.entity.financial.urbanitae.urbanitae_fetcher import (
            UrbanitaeFetcher,
        )
        from infrastructure.client.entity.financial.unicaja.unicaja_fetcher import (
            UnicajaFetcher,
        )
        from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
            TradeRepublicFetcher,
        )
        from infrastructure.client.entity.financial.ing.ing_fetcher import (
            INGFetcher,
        )
        from infrastructure.client.entity.financial.mintos.mintos_fetcher import (
            MintosFetcher,
        )
        from infrastructure.client.entity.financial.ibkr.ibkr_fetcher import (
            IBKRFetcher,
        )
        from infrastructure.client.entity.financial.wecity.wecity_fetcher import (
            WecityFetcher,
        )
        from finanze.infrastructure.client.entity.exchange.binance.binance_fetcher import (
            BinanceFetcher,
        )
        from infrastructure.crypto.public_key_derivation_adapter import (
            PublicKeyDerivationAdapter,
        )
        from infrastructure.table.csv_file_table_adapter import CSVFileTableAdapter
        from infrastructure.table.table_rw_dispatcher import TableRWDispatcher
        from infrastructure.table.xlsx_file_table_adapter import XLSXFileTableAdapter
        from infrastructure.templating.templated_data_generator import (
            TemplatedDataGenerator,
        )
        from infrastructure.templating.templated_data_parser import TemplateDataParser
        from infrastructure.file_storage.mobile_file_storage import MobileFileStorage
        from infrastructure.cloud.backup.capacitor_backup_processor import (
            CapacitorBackupProcessorAdapter,
        )
        from infrastructure.repository.keychain.public_keychain_repository import (
            PublicKeychainRepository,
        )
        from infrastructure.client.keychain.public_keychain_client import (
            PublicKeychainClient,
        )
        from infrastructure.keychain.public_keychain_adapter import (
            PublicKeychainAdapter,
        )
        from infrastructure.repository.historic.historic_repository import (
            HistoricSQLRepository as HistoricRepository,
        )
        from infrastructure.repository.sessions.sessions_repository import (
            SessionsRepository,
        )
        from infrastructure.repository.crypto.crypto_asset_repository import (
            CryptoAssetRegistryRepository,
        )
        from infrastructure.repository.templates.template_repository import (
            TemplateRepository,
        )
        from infrastructure.client.interests.ecb_client import ECBClient
        from application.use_cases.add_entity_credentials import (
            AddEntityCredentialsImpl,
        )
        from application.use_cases.connect_crypto_wallet import ConnectCryptoWalletImpl
        from application.use_cases.derive_crypto_addresses import (
            DeriveCryptoAddressesImpl,
        )
        from application.use_cases.export_file import ExportFileImpl
        from application.use_cases.fetch_crypto_data import FetchCryptoDataImpl
        from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
        from application.use_cases.import_file import ImportFileImpl
        from application.use_cases.import_backup import ImportBackupImpl
        from application.use_cases.upload_backup import UploadBackupImpl
        from application.use_cases.update_settings import UpdateSettingsImpl
        from application.use_cases.disconnect_entity import DisconnectEntityImpl
        from application.use_cases.update_crypto_wallet import (
            UpdateCryptoWalletConnectionImpl,
        )
        from application.use_cases.delete_crypto_wallet import (
            DeleteCryptoWalletConnectionImpl,
        )
        from application.use_cases.save_commodities import SaveCommoditiesImpl
        from application.use_cases.connect_external_integration import (
            ConnectExternalIntegrationImpl,
        )
        from application.use_cases.disconnect_external_integration import (
            DisconnectExternalIntegrationImpl,
        )
        from application.use_cases.save_periodic_flow import SavePeriodicFlowImpl
        from application.use_cases.update_periodic_flow import UpdatePeriodicFlowImpl
        from application.use_cases.delete_periodic_flow import DeletePeriodicFlowImpl
        from application.use_cases.save_pending_flows import SavePendingFlowsImpl
        from application.use_cases.create_real_estate import CreateRealEstateImpl
        from application.use_cases.update_real_estate import UpdateRealEstateImpl
        from application.use_cases.delete_real_estate import DeleteRealEstateImpl
        from application.use_cases.calculate_loan import CalculateLoanImpl
        from application.use_cases.calculate_savings import CalculateSavingsImpl
        from application.use_cases.get_euribor_rates import GetEuriborRatesImpl
        from application.use_cases.forecast import ForecastImpl
        from application.use_cases.update_contributions import UpdateContributionsImpl
        from application.use_cases.update_position import UpdatePositionImpl
        from application.use_cases.add_manual_transaction import (
            AddManualTransactionImpl,
        )
        from application.use_cases.update_manual_transaction import (
            UpdateManualTransactionImpl,
        )
        from application.use_cases.delete_manual_transaction import (
            DeleteManualTransactionImpl,
        )
        from application.use_cases.get_historic import GetHistoricImpl
        from application.use_cases.get_instruments import GetInstrumentsImpl
        from application.use_cases.get_instrument_info import GetInstrumentInfoImpl
        from application.use_cases.search_crypto_assets import SearchCryptoAssetsImpl
        from application.use_cases.get_crypto_asset_details import (
            GetCryptoAssetDetailsImpl,
        )
        from application.use_cases.get_templates import GetTemplatesImpl
        from application.use_cases.create_template import CreateTemplateImpl
        from application.use_cases.update_template import UpdateTemplateImpl
        from application.use_cases.delete_template import DeleteTemplateImpl
        from application.use_cases.get_template_fields import GetTemplateFieldsImpl
        from application.use_cases.save_backup_settings import SaveBackupSettingsImpl

        d = self._deferred
        core = self._core
        db_client = core.db_client

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
            domain.native_entities.MINTOS: MintosFetcher(),
            domain.native_entities.F24: F24Fetcher(),
            domain.native_entities.INDEXA_CAPITAL: IndexaCapitalFetcher(),
            domain.native_entities.ING: INGFetcher(),
            domain.native_entities.CAJAMAR: CajamarFetcher(),
            domain.native_entities.UNICAJA: UnicajaFetcher(use_mobile_client=True),
            domain.native_entities.IBKR: IBKRFetcher(),
            domain.native_entities.BINANCE: BinanceFetcher(),
        }
        external_integrations = {
            ExternalIntegrationId.ETHERSCAN: True,
            ExternalIntegrationId.ETHPLORER: True,
        }

        public_key_derivation = PublicKeyDerivationAdapter()

        csv_tsv_adapter = CSVFileTableAdapter()
        table_rw_adapter = TableRWDispatcher(
            {
                FileFormat.CSV: csv_tsv_adapter,
                FileFormat.TSV: csv_tsv_adapter,
                FileFormat.XLSX: XLSXFileTableAdapter(),
            }
        )

        template_gen = TemplatedDataGenerator()
        template_parser = TemplateDataParser()

        file_storage = MobileFileStorage()
        backup_processor = CapacitorBackupProcessorAdapter()

        public_keychain_data_repo = PublicKeychainRepository(client=db_client)
        public_keychain_fetcher = PublicKeychainClient()
        public_keychain = PublicKeychainAdapter(
            data_port=public_keychain_data_repo,
            fetcher_port=public_keychain_fetcher,
        )

        historic_repo = HistoricRepository(client=db_client)
        sessions_repo = SessionsRepository(client=db_client)
        crypto_asset_repo = CryptoAssetRegistryRepository(client=db_client)
        temp_repo = TemplateRepository(client=db_client)

        self.add_entity_creds = AddEntityCredentialsImpl(
            financial_entity_fetchers,
            d.creds_repo,
            sessions_repo,
            d.tx_handler,
            public_keychain,
            d.entity_account_repo,
        )

        self.fetch_financial = FetchFinancialDataImpl(
            d.position_repo,
            d.auto_repo,
            d.tx_repo,
            historic_repo,
            financial_entity_fetchers,
            d.config_loader,
            d.creds_repo,
            sessions_repo,
            d.last_fetches_repo,
            crypto_asset_repo,
            d.crypto_info,
            d.tx_handler,
            public_keychain,
            d.entity_account_repo,
            d.loan_calculator,
            d.re_repo,
        )
        self.fetch_crypto = FetchCryptoDataImpl(
            d.position_repo,
            crypto_entity_fetchers,
            d.wallet_repo,
            crypto_asset_repo,
            d.crypto_info,
            d.last_fetches_repo,
            d.ext_int_repo,
            d.tx_handler,
            public_key_derivation,
        )
        self.import_file = ImportFileImpl(
            d.position_repo,
            d.tx_repo,
            table_rw_adapter,
            d.entity_repo,
            d.virtual_repo,
            temp_repo,
            template_parser,
            d.tx_handler,
        )
        self.export_file = ExportFileImpl(
            d.position_repo,
            d.auto_repo,
            d.tx_repo,
            historic_repo,
            d.entity_repo,
            temp_repo,
            template_gen,
            table_rw_adapter,
        )

        self.conn_crypto = ConnectCryptoWalletImpl(
            d.wallet_repo,
            crypto_entity_fetchers,
            d.ext_int_repo,
            public_key_derivation,
            d.tx_handler,
        )
        self.derive_crypto = DeriveCryptoAddressesImpl(
            public_key_derivation, d.entity_repo
        )

        self.upload_backup = UploadBackupImpl(
            core.db_manager,
            d.backupable_ports,
            backup_processor,
            d.backup_repository,
            d.cloud_register,
            d.cloud_register,
        )
        self.import_backup = ImportBackupImpl(
            core.db_manager,
            d.backupable_ports,
            backup_processor,
            d.backup_repository,
            d.cloud_register,
            d.cloud_register,
        )

        self.update_settings = UpdateSettingsImpl(d.config_loader)
        self.disconnect_entity = DisconnectEntityImpl(
            d.creds_repo,
            sessions_repo,
            d.tx_handler,
            d.entity_account_repo,
            d.tx_repo,
            d.auto_repo,
            historic_repo,
        )

        self.up_crypto = UpdateCryptoWalletConnectionImpl(d.wallet_repo)
        self.del_crypto = DeleteCryptoWalletConnectionImpl(d.wallet_repo)

        self.save_commodities = SaveCommoditiesImpl(
            d.position_repo,
            d.ex_client,
            d.metal_client,
            d.last_fetches_repo,
            d.tx_handler,
        )

        self.conn_integration = ConnectExternalIntegrationImpl(
            d.ext_int_repo, external_integrations
        )
        self.disconn_integration = DisconnectExternalIntegrationImpl(d.ext_int_repo)

        self.save_periodic = SavePeriodicFlowImpl(d.period_repo)
        self.up_periodic = UpdatePeriodicFlowImpl(d.period_repo)
        self.del_periodic = DeletePeriodicFlowImpl(d.period_repo)
        self.save_pending = SavePendingFlowsImpl(d.pending_repo, d.tx_handler)

        self.create_re = CreateRealEstateImpl(
            d.re_repo, d.period_repo, d.tx_handler, file_storage
        )
        self.up_re = UpdateRealEstateImpl(
            d.re_repo, d.period_repo, d.tx_handler, file_storage
        )
        self.del_re = DeleteRealEstateImpl(
            d.re_repo, d.period_repo, d.tx_handler, file_storage
        )

        self.calc_loan = CalculateLoanImpl(d.loan_calculator)
        self.calc_savings = CalculateSavingsImpl()
        self.get_euribor = GetEuriborRatesImpl(ECBClient())

        self.forecast = ForecastImpl(
            d.position_repo,
            d.auto_repo,
            d.period_repo,
            d.pending_repo,
            d.re_repo,
            d.entity_repo,
        )

        self.up_contrib = UpdateContributionsImpl(
            d.entity_repo, d.auto_repo, d.virtual_repo, d.tx_handler
        )
        self.up_pos = UpdatePositionImpl(
            d.entity_repo,
            d.position_repo,
            d.manual_repo,
            d.virtual_repo,
            crypto_asset_repo,
            d.crypto_info,
            d.tx_handler,
            d.re_repo,
            d.loan_calculator,
        )
        self.add_manual_tx = AddManualTransactionImpl(
            d.entity_repo, d.tx_repo, d.virtual_repo, d.tx_handler
        )
        self.up_manual_tx = UpdateManualTransactionImpl(
            d.entity_repo, d.tx_repo, d.virtual_repo, d.tx_handler
        )
        self.del_manual_tx = DeleteManualTransactionImpl(
            d.tx_repo, d.virtual_repo, d.tx_handler
        )

        self.get_historic = GetHistoricImpl(historic_repo, d.entity_repo)
        self.get_instruments = GetInstrumentsImpl(d.inst_provider)
        self.get_inst_info = GetInstrumentInfoImpl(d.inst_provider)
        self.search_crypto = SearchCryptoAssetsImpl(d.crypto_info)
        self.get_crypto_details = GetCryptoAssetDetailsImpl(
            d.crypto_info, d.entity_repo
        )

        self.get_tmpl = GetTemplatesImpl(temp_repo)
        self.create_tmpl = CreateTemplateImpl(temp_repo)
        self.up_tmpl = UpdateTemplateImpl(temp_repo)
        self.del_tmpl = DeleteTemplateImpl(temp_repo)
        self.get_tmpl_fields = GetTemplateFieldsImpl()

        self.save_bkp_settings = SaveBackupSettingsImpl(d.cloud_register)
