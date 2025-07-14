from domain.use_cases.add_entity_credentials import AddEntityCredentials
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet
from domain.use_cases.connect_google import ConnectGoogle
from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection
from domain.use_cases.disconnect_entity import DisconnectEntity
from domain.use_cases.fetch_crypto_data import FetchCryptoData
from domain.use_cases.fetch_financial_data import FetchFinancialData
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.use_cases.get_contributions import GetContributions
from domain.use_cases.get_exchange_rates import GetExchangeRates
from domain.use_cases.get_external_integrations import GetExternalIntegrations
from domain.use_cases.get_login_status import GetLoginStatus
from domain.use_cases.get_position import GetPosition
from domain.use_cases.get_settings import GetSettings
from domain.use_cases.get_transactions import GetTransactions
from domain.use_cases.register_user import RegisterUser
from domain.use_cases.save_commodities import SaveCommodities
from domain.use_cases.update_crypto_wallet import UpdateCryptoWalletConnection
from domain.use_cases.update_settings import UpdateSettings
from domain.use_cases.update_sheets import UpdateSheets
from domain.use_cases.user_login import UserLogin
from domain.use_cases.user_logout import UserLogout
from domain.use_cases.virtual_fetch import VirtualFetch
from infrastructure.controller.config import FlaskApp
from infrastructure.controller.routes.add_entity_login import add_entity_login
from infrastructure.controller.routes.connect_crypto_wallet import connect_crypto_wallet
from infrastructure.controller.routes.connect_google import connect_google
from infrastructure.controller.routes.contributions import contributions
from infrastructure.controller.routes.delete_crypto_wallet import delete_crypto_wallet
from infrastructure.controller.routes.disconnect_entity import disconnect_entity
from infrastructure.controller.routes.exchange_rates import exchange_rates
from infrastructure.controller.routes.export import export
from infrastructure.controller.routes.fetch_crypto_data import fetch_crypto_data
from infrastructure.controller.routes.fetch_financial_data import fetch_financial_data
from infrastructure.controller.routes.get_available_sources import get_available_sources
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.controller.routes.get_settings import get_settings
from infrastructure.controller.routes.login_status import login_status
from infrastructure.controller.routes.logout import logout
from infrastructure.controller.routes.positions import positions
from infrastructure.controller.routes.register_user import register_user
from infrastructure.controller.routes.save_commodities import save_commodities
from infrastructure.controller.routes.transactions import transactions
from infrastructure.controller.routes.update_crypto_wallet import update_crypto_wallet
from infrastructure.controller.routes.update_settings import update_settings
from infrastructure.controller.routes.user_login import user_login
from infrastructure.controller.routes.virtual_fetch import virtual_fetch


def register_routes(
    app: FlaskApp,
    user_login_uc: UserLogin,
    register_user_uc: RegisterUser,
    get_available_entities_uc: GetAvailableEntities,
    fetch_financial_data_uc: FetchFinancialData,
    fetch_crypto_data_uc: FetchCryptoData,
    update_sheets_uc: UpdateSheets,
    virtual_fetch_uc: VirtualFetch,
    add_entity_credentials_uc: AddEntityCredentials,
    get_login_status_uc: GetLoginStatus,
    user_logout_uc: UserLogout,
    get_settings_uc: GetSettings,
    update_settings_uc: UpdateSettings,
    disconnect_entity_uc: DisconnectEntity,
    get_position_uc: GetPosition,
    get_contributions_uc: GetContributions,
    get_transactions_uc: GetTransactions,
    get_exchange_rates_uc: GetExchangeRates,
    connect_crypto_wallet_uc: ConnectCryptoWallet,
    update_crypto_wallet_uc: UpdateCryptoWalletConnection,
    delete_crypto_wallet_uc: DeleteCryptoWalletConnection,
    save_commodities_uc: SaveCommodities,
    get_external_integrations_uc: GetExternalIntegrations,
    connect_google_uc: ConnectGoogle,
):
    @app.route("/api/v1/login", methods=["POST"])
    def user_login_route():
        return user_login(user_login_uc)

    @app.route("/api/v1/signup", methods=["POST"])
    def register_user_route():
        return register_user(register_user_uc)

    @app.route("/api/v1/login", methods=["GET"])
    def login_status_route():
        return login_status(get_login_status_uc)

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

    @app.route("/api/v1/fetch/financial", methods=["POST"])
    async def fetch_financial_data_route():
        return await fetch_financial_data(fetch_financial_data_uc)

    @app.route("/api/v1/fetch/crypto", methods=["POST"])
    async def fetch_crypto_data_route():
        return await fetch_crypto_data(fetch_crypto_data_uc)

    @app.route("/api/v1/fetch/virtual", methods=["POST"])
    async def virtual_fetch_route():
        return await virtual_fetch(virtual_fetch_uc)

    @app.route("/api/v1/export", methods=["POST"])
    async def export_route():
        return await export(update_sheets_uc)

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

    @app.route("/api/v1/integrations/google", methods=["POST"])
    def connect_google_route():
        return connect_google(connect_google_uc)
