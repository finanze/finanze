from domain.use_cases.add_entity_credentials import AddEntityCredentials
from domain.use_cases.disconnect_entity import DisconnectEntity
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.use_cases.get_contributions import GetContributions
from domain.use_cases.get_login_status import GetLoginStatus
from domain.use_cases.get_position import GetPosition
from domain.use_cases.get_settings import GetSettings
from domain.use_cases.get_transactions import GetTransactions
from domain.use_cases.register_user import RegisterUser
from domain.use_cases.scrape import Scrape
from domain.use_cases.update_settings import UpdateSettings
from domain.use_cases.update_sheets import UpdateSheets
from domain.use_cases.user_login import UserLogin
from domain.use_cases.user_logout import UserLogout
from domain.use_cases.virtual_scrape import VirtualScrape
from infrastructure.controller.config import FlaskApp
from infrastructure.controller.routes.add_entity_login import add_entity_login
from infrastructure.controller.routes.contributions import contributions
from infrastructure.controller.routes.disconnect_entity import disconnect_entity
from infrastructure.controller.routes.export import export
from infrastructure.controller.routes.get_available_sources import get_available_sources
from infrastructure.controller.routes.get_settings import get_settings
from infrastructure.controller.routes.login_status import login_status
from infrastructure.controller.routes.logout import logout
from infrastructure.controller.routes.positions import positions
from infrastructure.controller.routes.register_user import register_user
from infrastructure.controller.routes.scrape import scrape
from infrastructure.controller.routes.transactions import transactions
from infrastructure.controller.routes.update_settings import update_settings
from infrastructure.controller.routes.user_login import user_login
from infrastructure.controller.routes.virtual_scrape import virtual_scrape


def register_routes(
    app: FlaskApp,
    user_login_uc: UserLogin,
    register_user_uc: RegisterUser,
    get_available_entities_uc: GetAvailableEntities,
    scrape_uc: Scrape,
    update_sheets_uc: UpdateSheets,
    virtual_scrape_uc: VirtualScrape,
    add_entity_credentials_uc: AddEntityCredentials,
    get_login_status_uc: GetLoginStatus,
    user_logout_uc: UserLogout,
    get_settings_uc: GetSettings,
    update_settings_uc: UpdateSettings,
    disconnect_entity_uc: DisconnectEntity,
    get_position_uc: GetPosition,
    get_contributions_uc: GetContributions,
    get_transactions_uc: GetTransactions,
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
    async def get_available_source_route():
        return await get_available_sources(get_available_entities_uc)

    @app.route("/api/v1/entities/login", methods=["POST"])
    async def add_entity_login_route():
        return await add_entity_login(add_entity_credentials_uc)

    @app.route("/api/v1/entities/login", methods=["DELETE"])
    async def disconnect_entity_route():
        return await disconnect_entity(disconnect_entity_uc)

    @app.route("/api/v1/scrape", methods=["POST"])
    async def scrape_route():
        return await scrape(scrape_uc)

    @app.route("/api/v1/scrape/virtual", methods=["POST"])
    async def virtual_scrape_route():
        return await virtual_scrape(virtual_scrape_uc)

    @app.route("/api/v1/export", methods=["POST"])
    def export_route():
        return export(update_sheets_uc)

    @app.route("/api/v1/positions", methods=["GET"])
    def positions_route():
        return positions(get_position_uc)

    @app.route("/api/v1/contributions", methods=["GET"])
    def contributions_route():
        return contributions(get_contributions_uc)

    @app.route("/api/v1/transactions", methods=["GET"])
    def transactions_route():
        return transactions(get_transactions_uc)
