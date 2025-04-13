import logging
import os
from logging import getLevelName

from flask_cors import CORS
from waitress import serve

import domain.native_entities
from application.use_cases.get_available_sources import GetAvailableSourcesImpl
from application.use_cases.scrape import ScrapeImpl
from application.use_cases.update_sheets import UpdateSheetsImpl
from application.use_cases.virtual_scrape import VirtualScrapeImpl
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.controller import exception_handler
from infrastructure.controller.config import FlaskApp
from infrastructure.controller.controllers import Controllers
from infrastructure.credentials.credentials_reader import CredentialsReader
from infrastructure.repository import AutoContributionsRepository, HistoricRepository, PositionRepository, \
    TransactionRepository, EntityRepository
from infrastructure.repository.db.setup import initialize_database
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.scrapers.f24.f24_scraper import F24Scraper
from infrastructure.scrapers.mintos.mintos_scraper import MintosScraper
from infrastructure.scrapers.myinvestor import MyInvestorScraper
from infrastructure.scrapers.sego.sego_scraper import SegoScraper
from infrastructure.scrapers.tr.trade_republic_scraper import TradeRepublicScraper
from infrastructure.scrapers.unicaja.unicaja_scraper import UnicajaScraper
from infrastructure.scrapers.urbanitae.urbanitae_scraper import UrbanitaeScraper
from infrastructure.scrapers.wecity.wecity_scraper import WecityScraper
from infrastructure.sheets.exporter.sheets_exporter import SheetsExporter
from infrastructure.sheets.importer.sheets_importer import SheetsImporter

log_level = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig()
logging.getLogger().setLevel(getLevelName(log_level))

#db_client = initialize_database("bank_data.db")
db_client = initialize_database("bank_data_db_old")

update_cooldown = os.environ.get("UPDATE_COOLDOWN", 60)
config_path = os.environ.get("CONFIG_PATH", "config.yml")

config_loader = ConfigLoader(config_path)
config_loader.check_or_create_default_config()

entity_scrapers = {
    domain.native_entities.MY_INVESTOR: MyInvestorScraper(),
    domain.native_entities.TRADE_REPUBLIC: TradeRepublicScraper(),
    domain.native_entities.UNICAJA: UnicajaScraper(),
    domain.native_entities.URBANITAE: UrbanitaeScraper(),
    domain.native_entities.WECITY: WecityScraper(),
    domain.native_entities.SEGO: SegoScraper(),
    domain.native_entities.MINTOS: MintosScraper(),
    domain.native_entities.F24: F24Scraper(),
}
virtual_scraper = SheetsImporter()
position_repository = PositionRepository(client=db_client)
auto_contrib_repository = AutoContributionsRepository(client=db_client)
transaction_repository = TransactionRepository(client=db_client)
historic_repository = HistoricRepository(client=db_client)
entity_repository = EntityRepository(client=db_client)

transaction_handler = TransactionHandler(client=db_client)

credentials_reader = CredentialsReader()

get_available_sources = GetAvailableSourcesImpl(
    config_loader,
    credentials_reader
)
scrape = ScrapeImpl(
    update_cooldown,
    position_repository,
    auto_contrib_repository,
    transaction_repository,
    historic_repository,
    entity_scrapers,
    config_loader,
    credentials_reader,
    transaction_handler
)
update_sheets = UpdateSheetsImpl(
    position_repository,
    auto_contrib_repository,
    transaction_repository,
    historic_repository,
    SheetsExporter(),
    config_loader
)
virtual_scrape = VirtualScrapeImpl(
    position_repository,
    transaction_repository,
    virtual_scraper,
    entity_repository,
    config_loader,
    transaction_handler
)

controllers = Controllers(get_available_sources, scrape, update_sheets, virtual_scrape)

app = FlaskApp(__name__)
CORS(app)
port = os.environ.get("WEB_PORT", 8080)

app.add_url_rule('/api/v1/scrape', view_func=controllers.get_available_sources, methods=['GET'])
app.add_url_rule('/api/v1/scrape', view_func=controllers.scrape, methods=['POST'])
app.add_url_rule('/api/v1/scrape/virtual', view_func=controllers.virtual_scrape, methods=['POST'])
app.add_url_rule('/api/v1/update-sheets', view_func=controllers.update_sheets, methods=['POST'])
app.register_error_handler(500, exception_handler.handle_unexpected_error)

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=port)
