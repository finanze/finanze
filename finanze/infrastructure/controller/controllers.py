from domain.use_cases.add_entity_credentials import AddEntityCredentials
from domain.use_cases.add_manual_transaction import AddManualTransaction
from domain.use_cases.calculate_loan import CalculateLoan
from domain.use_cases.calculate_savings import CalculateSavings
from domain.use_cases.change_user_password import ChangeUserPassword
from domain.use_cases.complete_external_entity_connection import (
    CompleteExternalEntityConnection,
)
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet
from domain.use_cases.connect_external_entity import ConnectExternalEntity
from domain.use_cases.connect_external_integration import ConnectExternalIntegration
from domain.use_cases.create_real_estate import CreateRealEstate
from domain.use_cases.create_template import CreateTemplate
from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection
from domain.use_cases.delete_external_entity import DeleteExternalEntity
from domain.use_cases.delete_manual_transaction import DeleteManualTransaction
from domain.use_cases.delete_periodic_flow import DeletePeriodicFlow
from domain.use_cases.delete_real_estate import DeleteRealEstate
from domain.use_cases.delete_template import DeleteTemplate
from domain.use_cases.disconnect_entity import DisconnectEntity
from domain.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegration,
)
from domain.use_cases.export_file import ExportFile
from domain.use_cases.export_sheets import ExportSheets
from domain.use_cases.fetch_crypto_data import FetchCryptoData
from domain.use_cases.fetch_external_financial_data import FetchExternalFinancialData
from domain.use_cases.fetch_financial_data import FetchFinancialData
from domain.use_cases.forecast import Forecast
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.use_cases.get_available_external_entities import (
    GetAvailableExternalEntities,
)
from domain.use_cases.get_backup_settings import GetBackupSettings
from domain.use_cases.get_backups import GetBackups
from domain.use_cases.get_cloud_auth import GetCloudAuth
from domain.use_cases.get_contributions import GetContributions
from domain.use_cases.get_crypto_asset_details import GetCryptoAssetDetails
from domain.use_cases.get_exchange_rates import GetExchangeRates
from domain.use_cases.get_external_integrations import GetExternalIntegrations
from domain.use_cases.get_historic import GetHistoric
from domain.use_cases.get_instrument_info import GetInstrumentInfo
from domain.use_cases.get_instruments import GetInstruments
from domain.use_cases.get_money_events import GetMoneyEvents
from domain.use_cases.get_pending_flows import GetPendingFlows
from domain.use_cases.get_periodic_flows import GetPeriodicFlows
from domain.use_cases.get_position import GetPosition
from domain.use_cases.get_settings import GetSettings
from domain.use_cases.get_status import GetStatus
from domain.use_cases.get_template_fields import GetTemplateFields
from domain.use_cases.get_templates import GetTemplates
from domain.use_cases.get_transactions import GetTransactions
from domain.use_cases.handle_cloud_auth import HandleCloudAuth
from domain.use_cases.import_backup import ImportBackup
from domain.use_cases.import_file import ImportFile
from domain.use_cases.import_sheets import ImportSheets
from domain.use_cases.list_real_estate import ListRealEstate
from domain.use_cases.register_user import RegisterUser
from domain.use_cases.save_backup_settings import SaveBackupSettings
from domain.use_cases.save_commodities import SaveCommodities
from domain.use_cases.save_pending_flows import SavePendingFlows
from domain.use_cases.save_periodic_flow import SavePeriodicFlow
from domain.use_cases.search_crypto_assets import SearchCryptoAssets
from domain.use_cases.update_contributions import UpdateContributions
from domain.use_cases.update_crypto_wallet import UpdateCryptoWalletConnection
from domain.use_cases.update_manual_transaction import UpdateManualTransaction
from domain.use_cases.update_periodic_flow import UpdatePeriodicFlow
from domain.use_cases.update_position import UpdatePosition
from domain.use_cases.update_real_estate import UpdateRealEstate
from domain.use_cases.update_settings import UpdateSettings
from domain.use_cases.update_template import UpdateTemplate
from domain.use_cases.update_tracked_quotes import UpdateTrackedQuotes
from domain.use_cases.upload_backup import UploadBackup
from domain.use_cases.user_login import UserLogin
from domain.use_cases.user_logout import UserLogout
from infrastructure.controller.config import FlaskApp
from infrastructure.controller.routes.add_entity_login import add_entity_login
from infrastructure.controller.routes.add_manual_transaction import (
    add_manual_transaction,
)
from infrastructure.controller.routes.calculate_loan import calculate_loan
from infrastructure.controller.routes.calculate_savings import calculate_savings
from infrastructure.controller.routes.change_user_password import change_user_password
from infrastructure.controller.routes.complete_external_entity_connection import (
    complete_external_entity_connection,
)
from infrastructure.controller.routes.connect_crypto_wallet import connect_crypto_wallet
from infrastructure.controller.routes.connect_external_entity import (
    connect_external_entity,
)
from infrastructure.controller.routes.connect_external_integration import (
    connect_external_integration,
)
from infrastructure.controller.routes.contributions import contributions
from infrastructure.controller.routes.create_real_estate import create_real_estate
from infrastructure.controller.routes.create_template import create_template
from infrastructure.controller.routes.delete_crypto_wallet import delete_crypto_wallet
from infrastructure.controller.routes.delete_external_entity import (
    delete_external_entity,
)
from infrastructure.controller.routes.delete_manual_transaction import (
    delete_manual_transaction,
)
from infrastructure.controller.routes.delete_periodic_flow import delete_periodic_flow
from infrastructure.controller.routes.delete_real_estate import delete_real_estate
from infrastructure.controller.routes.delete_template import delete_template
from infrastructure.controller.routes.disconnect_entity import disconnect_entity
from infrastructure.controller.routes.disconnect_external_integration import (
    disconnect_external_integration,
)
from infrastructure.controller.routes.exchange_rates import exchange_rates
from infrastructure.controller.routes.export_file import export_file
from infrastructure.controller.routes.export_sheets import export_sheets
from infrastructure.controller.routes.fetch_crypto_data import fetch_crypto_data
from infrastructure.controller.routes.fetch_external_financial_data import (
    fetch_external_financial_data,
)
from infrastructure.controller.routes.fetch_financial_data import fetch_financial_data
from infrastructure.controller.routes.forecast import forecast
from infrastructure.controller.routes.get_available_external_entities import (
    get_available_external_entities,
)
from infrastructure.controller.routes.get_crypto_asset_details import (
    get_crypto_asset_details,
)
from infrastructure.controller.routes.get_available_sources import get_available_sources
from infrastructure.controller.routes.get_backup_settings import get_backup_settings
from infrastructure.controller.routes.get_backups import get_backups
from infrastructure.controller.routes.get_cloud_auth import get_cloud_auth
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.controller.routes.get_money_events import get_money_events
from infrastructure.controller.routes.get_pending_flows import get_pending_flows
from infrastructure.controller.routes.get_periodic_flows import get_periodic_flows
from infrastructure.controller.routes.get_settings import get_settings
from infrastructure.controller.routes.get_status import status
from infrastructure.controller.routes.get_template_fields_route import (
    get_template_fields,
)
from infrastructure.controller.routes.get_templates import get_templates
from infrastructure.controller.routes.handle_cloud_auth import handle_cloud_auth
from infrastructure.controller.routes.historic import get_historic
from infrastructure.controller.routes.import_backup import import_backup
from infrastructure.controller.routes.import_file import import_file_route
from infrastructure.controller.routes.import_sheets import import_sheets
from infrastructure.controller.routes.instrument_details import instrument_details
from infrastructure.controller.routes.instruments import instruments
from infrastructure.controller.routes.list_real_estate import list_real_estate
from infrastructure.controller.routes.logout import logout
from infrastructure.controller.routes.oauth_callback import oauth_callback
from infrastructure.controller.routes.positions import positions
from infrastructure.controller.routes.register_user import register_user
from infrastructure.controller.routes.save_backup_settings import save_backup_settings
from infrastructure.controller.routes.save_commodities import save_commodities
from infrastructure.controller.routes.save_pending_flows import save_pending_flows
from infrastructure.controller.routes.save_periodic_flow import save_periodic_flow
from infrastructure.controller.routes.transactions import transactions
from infrastructure.controller.routes.update_contributions import update_contributions
from infrastructure.controller.routes.update_crypto_wallet import update_crypto_wallet
from infrastructure.controller.routes.update_manual_transaction import (
    update_manual_transaction,
)
from infrastructure.controller.routes.update_periodic_flow import update_periodic_flow
from infrastructure.controller.routes.update_position import update_position
from infrastructure.controller.routes.update_real_estate import update_real_estate
from infrastructure.controller.routes.update_settings import update_settings
from infrastructure.controller.routes.update_template import update_template
from infrastructure.controller.routes.update_tracked_quotes import update_tracked_quotes
from infrastructure.controller.routes.upload_backup import upload_backup
from infrastructure.controller.routes.user_login import user_login
from infrastructure.controller.routes.search_crypto_assets import search_crypto_assets


def register_routes(
    app: FlaskApp,
    user_login_uc: UserLogin,
    register_user_uc: RegisterUser,
    change_user_password_uc: ChangeUserPassword,
    get_available_entities_uc: GetAvailableEntities,
    fetch_financial_data_uc: FetchFinancialData,
    fetch_crypto_data_uc: FetchCryptoData,
    fetch_external_financial_data_uc: FetchExternalFinancialData,
    export_sheets_uc: ExportSheets,
    export_file_uc: ExportFile,
    import_sheets_uc: ImportSheets,
    import_file_uc: ImportFile,
    add_entity_credentials_uc: AddEntityCredentials,
    get_status_uc: GetStatus,
    user_logout_uc: UserLogout,
    get_settings_uc: GetSettings,
    update_settings_uc: UpdateSettings,
    disconnect_entity_uc: DisconnectEntity,
    get_position_uc: GetPosition,
    get_contributions_uc: GetContributions,
    get_historic_uc: GetHistoric,
    get_transactions_uc: GetTransactions,
    get_exchange_rates_uc: GetExchangeRates,
    get_money_events_uc: GetMoneyEvents,
    connect_external_entity_uc: ConnectExternalEntity,
    complete_external_entity_connection_uc: CompleteExternalEntityConnection,
    delete_external_entity_uc: DeleteExternalEntity,
    get_available_external_entities_uc: GetAvailableExternalEntities,
    connect_crypto_wallet_uc: ConnectCryptoWallet,
    update_crypto_wallet_uc: UpdateCryptoWalletConnection,
    delete_crypto_wallet_uc: DeleteCryptoWalletConnection,
    save_commodities_uc: SaveCommodities,
    get_external_integrations_uc: GetExternalIntegrations,
    connect_external_integrations_uc: ConnectExternalIntegration,
    disconnect_external_integrations_uc: DisconnectExternalIntegration,
    save_periodic_flow_uc: SavePeriodicFlow,
    update_periodic_flow_uc: UpdatePeriodicFlow,
    delete_periodic_flow_uc: DeletePeriodicFlow,
    get_periodic_flows_uc: GetPeriodicFlows,
    save_pending_flows_uc: SavePendingFlows,
    get_pending_flows_uc: GetPendingFlows,
    create_real_estate_uc: CreateRealEstate,
    update_real_estate_uc: UpdateRealEstate,
    delete_real_estate_uc: DeleteRealEstate,
    list_real_estate_uc: ListRealEstate,
    calculate_loan_uc: CalculateLoan,
    calculate_savings_uc: CalculateSavings,
    forecast_uc: Forecast,
    update_contributions_uc: UpdateContributions,
    update_position_uc: UpdatePosition,
    add_manual_transaction_uc: AddManualTransaction,
    update_manual_transaction_uc: UpdateManualTransaction,
    delete_manual_transaction_uc: DeleteManualTransaction,
    get_instruments_uc: GetInstruments,
    get_instrument_info_uc: GetInstrumentInfo,
    update_tracked_quotes_uc: UpdateTrackedQuotes,
    search_crypto_assets_uc: SearchCryptoAssets,
    get_crypto_asset_details_uc: GetCryptoAssetDetails,
    create_template_uc: CreateTemplate,
    update_template_uc: UpdateTemplate,
    delete_template_uc: DeleteTemplate,
    get_templates_uc: GetTemplates,
    get_template_fields_uc: GetTemplateFields,
    upload_backup_uc: UploadBackup,
    import_backup_uc: ImportBackup,
    get_backups_uc: GetBackups,
    handle_cloud_auth_uc: HandleCloudAuth,
    get_cloud_auth_uc: GetCloudAuth,
    get_backup_settings_uc: GetBackupSettings,
    save_backup_settings_uc: SaveBackupSettings,
):
    @app.route("/api/v1/login", methods=["POST"])
    def user_login_route():
        return user_login(user_login_uc)

    @app.route("/api/v1/signup", methods=["POST"])
    def register_user_route():
        return register_user(register_user_uc)

    @app.route("/api/v1/change-password", methods=["POST"])
    def change_user_password_route():
        return change_user_password(change_user_password_uc)

    @app.route("/api/v1/status", methods=["GET"])
    def get_status_route():
        return status(get_status_uc)

    @app.route("/api/v1/logout", methods=["POST"])
    def logout_route():
        return logout(user_logout_uc)

    @app.route("/api/v1/settings", methods=["GET"])
    def settings_route():
        return get_settings(get_settings_uc)

    @app.route("/api/v1/settings", methods=["POST"])
    def update_settings_route():
        return update_settings(update_settings_uc)

    @app.route("/api/v1/entities", methods=["GET"])
    def get_available_source_route():
        return get_available_sources(get_available_entities_uc)

    @app.route("/api/v1/entities/login", methods=["POST"])
    async def add_entity_login_route():
        return await add_entity_login(add_entity_credentials_uc)

    @app.route("/api/v1/entities/login", methods=["DELETE"])
    async def disconnect_entity_route():
        return await disconnect_entity(disconnect_entity_uc)

    @app.route("/api/v1/entities/external/candidates", methods=["GET"])
    async def get_external_entity_candidates_route():
        return await get_available_external_entities(get_available_external_entities_uc)

    @app.route("/api/v1/entities/external", methods=["POST"])
    async def connect_external_entity_route():
        return await connect_external_entity(connect_external_entity_uc)

    @app.route("/api/v1/entities/external/complete", methods=["GET"])
    async def complete_external_entity_connection_route():
        return await complete_external_entity_connection(
            complete_external_entity_connection_uc
        )

    @app.route("/api/v1/entities/external/<external_entity_id>", methods=["DELETE"])
    async def disconnect_external_entity_route(external_entity_id: str):
        return await delete_external_entity(
            delete_external_entity_uc, external_entity_id
        )

    @app.route("/api/v1/data/fetch/financial", methods=["POST"])
    async def fetch_financial_data_route():
        return await fetch_financial_data(fetch_financial_data_uc)

    @app.route("/api/v1/data/fetch/crypto", methods=["POST"])
    async def fetch_crypto_data_route():
        return await fetch_crypto_data(fetch_crypto_data_uc)

    @app.route("/api/v1/data/import/sheets", methods=["POST"])
    async def import_sheets_route():
        return await import_sheets(import_sheets_uc)

    @app.route("/api/v1/data/import/file", methods=["POST"])
    async def import_file_endpoint():
        return await import_file_route(import_file_uc)

    @app.route("/api/v1/data/fetch/external/<external_entity_id>", methods=["POST"])
    async def fetch_external_entity_route(external_entity_id: str):
        return await fetch_external_financial_data(
            fetch_external_financial_data_uc, external_entity_id
        )

    @app.route("/api/v1/data/export/sheets", methods=["POST"])
    async def export_sheets_route():
        return await export_sheets(export_sheets_uc)

    @app.route("/api/v1/data/export/file", methods=["POST"])
    async def export_file_route():
        return await export_file(export_file_uc)

    @app.route("/api/v1/positions", methods=["GET"])
    def positions_route():
        return positions(get_position_uc)

    @app.route("/api/v1/contributions", methods=["GET"])
    def contributions_route():
        return contributions(get_contributions_uc)

    @app.route("/api/v1/transactions", methods=["GET"])
    def transactions_route():
        return transactions(get_transactions_uc)

    @app.route("/api/v1/exchange-rates", methods=["GET"])
    def exchange_rates_route():
        return exchange_rates(get_exchange_rates_uc)

    @app.route("/api/v1/events", methods=["GET"])
    def get_money_events_route():
        return get_money_events(get_money_events_uc)

    @app.route("/api/v1/crypto-wallet", methods=["POST"])
    def connect_crypto_wallet_route():
        return connect_crypto_wallet(connect_crypto_wallet_uc)

    @app.route("/api/v1/crypto-wallet", methods=["PUT"])
    def update_crypto_wallet_route():
        return update_crypto_wallet(update_crypto_wallet_uc)

    @app.route("/api/v1/crypto-wallet/<wallet_connection_id>", methods=["DELETE"])
    def delete_crypto_wallet_route(wallet_connection_id: str):
        return delete_crypto_wallet(delete_crypto_wallet_uc, wallet_connection_id)

    @app.route("/api/v1/commodities", methods=["POST"])
    async def save_commodities_route():
        return await save_commodities(save_commodities_uc)

    @app.route("/api/v1/integrations", methods=["GET"])
    def get_external_integrations_route():
        return get_external_integrations(get_external_integrations_uc)

    @app.route("/api/v1/integrations/<integration_id>", methods=["POST"])
    def connect_external_integration_route(integration_id: str):
        return connect_external_integration(
            connect_external_integrations_uc, integration_id
        )

    @app.route("/api/v1/integrations/<integration_id>", methods=["DELETE"])
    def disconnect_external_integration_route(integration_id: str):
        return disconnect_external_integration(
            disconnect_external_integrations_uc, integration_id
        )

    @app.route("/api/v1/flows/periodic", methods=["POST"])
    def save_periodic_flow_route():
        return save_periodic_flow(save_periodic_flow_uc)

    @app.route("/api/v1/flows/periodic", methods=["PUT"])
    def update_periodic_flow_route():
        return update_periodic_flow(update_periodic_flow_uc)

    @app.route("/api/v1/flows/periodic/<flow_id>", methods=["DELETE"])
    def delete_periodic_flow_route(flow_id: str):
        return delete_periodic_flow(delete_periodic_flow_uc, flow_id)

    @app.route("/api/v1/flows/periodic", methods=["GET"])
    def get_periodic_flows_route():
        return get_periodic_flows(get_periodic_flows_uc)

    @app.route("/api/v1/flows/pending", methods=["POST"])
    async def save_pending_flows_route():
        return await save_pending_flows(save_pending_flows_uc)

    @app.route("/api/v1/flows/pending", methods=["GET"])
    def get_pending_flows_route():
        return get_pending_flows(get_pending_flows_uc)

    @app.route("/api/v1/real-estate", methods=["GET"])
    def list_real_estate_route():
        return list_real_estate(list_real_estate_uc)

    @app.route("/api/v1/real-estate", methods=["POST"])
    async def create_real_estate_route():
        return await create_real_estate(create_real_estate_uc)

    @app.route("/api/v1/real-estate", methods=["PUT"])
    async def update_real_estate_route():
        return await update_real_estate(update_real_estate_uc)

    @app.route("/api/v1/real-estate/<real_estate_id>", methods=["DELETE"])
    async def delete_real_estate_route(real_estate_id: str):
        return await delete_real_estate(delete_real_estate_uc, real_estate_id)

    @app.route("/api/v1/calculation/loan", methods=["POST"])
    def calculate_loan_route():
        return calculate_loan(calculate_loan_uc)

    @app.route("/api/v1/forecast", methods=["POST"])
    def forecast_route():
        return forecast(forecast_uc)

    @app.route("/api/v1/data/manual/contributions", methods=["POST"])
    async def update_contributions_route():
        return await update_contributions(update_contributions_uc)

    @app.route("/api/v1/data/manual/positions", methods=["POST"])
    async def update_position_route():
        return await update_position(update_position_uc)

    @app.route("/api/v1/data/manual/transactions", methods=["POST"])
    async def add_manual_transaction_route():
        return await add_manual_transaction(add_manual_transaction_uc)

    @app.route("/api/v1/data/manual/transactions/<tx_id>", methods=["PUT"])
    async def update_manual_transaction_route(tx_id: str):
        return await update_manual_transaction(update_manual_transaction_uc, tx_id)

    @app.route("/api/v1/data/manual/transactions/<tx_id>", methods=["DELETE"])
    async def delete_manual_transaction_route(tx_id: str):
        return await delete_manual_transaction(delete_manual_transaction_uc, tx_id)

    @app.route("/api/v1/historic", methods=["GET"])
    def get_historic_route():
        return get_historic(get_historic_uc)

    @app.route("/api/v1/assets/instruments", methods=["GET"])
    def instruments_route():
        return instruments(get_instruments_uc)

    @app.route("/api/v1/assets/instruments/details", methods=["GET"])
    def instrument_details_route():
        return instrument_details(get_instrument_info_uc)

    @app.route("/api/v1/assets/crypto", methods=["GET"])
    def crypto_assets_route():
        return search_crypto_assets(search_crypto_assets_uc)

    @app.route("/api/v1/assets/crypto/<asset_id>", methods=["GET"])
    def crypto_asset_details_route(asset_id: str):
        return get_crypto_asset_details(get_crypto_asset_details_uc, asset_id)

    @app.route("/api/v1/data/manual/positions/update-quotes", methods=["POST"])
    async def update_tracked_quotes_route():
        return await update_tracked_quotes(update_tracked_quotes_uc)

    @app.route("/api/v1/templates", methods=["GET"])
    def get_templates_route():
        return get_templates(get_templates_uc)

    @app.route("/api/v1/templates", methods=["POST"])
    def create_template_route():
        return create_template(create_template_uc)

    @app.route("/api/v1/templates", methods=["PUT"])
    def update_template_route():
        return update_template(update_template_uc)

    @app.route("/api/v1/templates/<template_id>", methods=["DELETE"])
    def delete_template_route(template_id: str):
        return delete_template(delete_template_uc, template_id)

    @app.route("/api/v1/templates/fields", methods=["GET"])
    def get_template_fields_route():
        return get_template_fields(get_template_fields_uc)

    @app.route("/api/v1/calculations/savings", methods=["POST"])
    def calculate_savings_route():
        return calculate_savings(calculate_savings_uc)

    @app.route("/api/v1/cloud/backup/upload", methods=["POST"])
    def upload_backup_route():
        return upload_backup(upload_backup_uc)

    @app.route("/api/v1/cloud/backup/import", methods=["POST"])
    def import_backup_route():
        return import_backup(import_backup_uc)

    @app.route("/api/v1/cloud/backup", methods=["GET"])
    def get_backups_route():
        return get_backups(get_backups_uc)

    @app.route("/api/v1/cloud/auth", methods=["POST"])
    def handle_cloud_auth_route():
        return handle_cloud_auth(handle_cloud_auth_uc)

    @app.route("/api/v1/cloud/auth", methods=["GET"])
    def get_cloud_auth_route():
        return get_cloud_auth(get_cloud_auth_uc)

    @app.route("/api/v1/cloud/backup/settings", methods=["GET"])
    def get_backup_settings_route():
        return get_backup_settings(get_backup_settings_uc)

    @app.route("/api/v1/cloud/backup/settings", methods=["POST"])
    def save_backup_settings_route():
        return save_backup_settings(save_backup_settings_uc)

    @app.route("/oauth/callback", methods=["GET"])
    def oauth_callback_route():
        return oauth_callback()
