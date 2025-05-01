from domain.use_cases.add_entity_credentials import AddEntityCredentials
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.use_cases.scrape import Scrape
from domain.use_cases.update_sheets import UpdateSheets
from domain.use_cases.user_login import UserLogin
from domain.use_cases.virtual_scrape import VirtualScrape
from infrastructure.controller.config import FlaskApp
from infrastructure.controller.routes.add_entity_login import add_entity_login
from infrastructure.controller.routes.get_available_sources import get_available_sources
from infrastructure.controller.routes.scrape import scrape
from infrastructure.controller.routes.update_sheets import update_sheets
from infrastructure.controller.routes.user_login import user_login
from infrastructure.controller.routes.virtual_scrape import virtual_scrape


def register_routes(app: FlaskApp,
                    user_login_uc: UserLogin,
                    get_available_entities_uc: GetAvailableEntities,
                    scrape_uc: Scrape,
                    update_sheets_uc: UpdateSheets,
                    virtual_scrape_uc: VirtualScrape,
                    add_entity_credentials_uc: AddEntityCredentials):
    @app.route('/api/v1/login', methods=['POST'])
    def user_login_route():
        return user_login(user_login_uc)

    @app.route('/api/v1/scrape')
    async def get_available_source_route():
        return await get_available_sources(get_available_entities_uc)

    @app.route('/api/v1/scrape', methods=['POST'])
    async def scrape_route():
        return await scrape(scrape_uc)

    @app.route('/api/v1/entity/login', methods=['POST'])
    async def add_entity_login_route():
        return await add_entity_login(add_entity_credentials_uc)

    @app.route('/api/v1/scrape/virtual', methods=['POST'])
    async def virtual_scrape_route():
        return await virtual_scrape(virtual_scrape_uc)

    @app.route('/api/v1/update-sheets', methods=['POST'])
    def update_sheets_route():
        return update_sheets(update_sheets_uc)
