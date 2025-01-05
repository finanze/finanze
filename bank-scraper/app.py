import logging
import os
from logging import getLevelName

from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient
from waitress import serve

from application.use_cases.get_available_sources import GetAvailableSourcesImpl
from application.use_cases.scrape import ScrapeImpl
from application.use_cases.update_sheets import UpdateSheetsImpl
from application.use_cases.virtual_scrape import VirtualScrapeImpl
from domain.financial_entity import Entity
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.controller.controllers import Controllers
from infrastructure.repository.auto_contributions_repository import AutoContributionsRepository
from infrastructure.repository.position_repository import PositionRepository
from infrastructure.repository.transaction_repository import TransactionRepository
from infrastructure.scrapers.myinvestor.myinvestor_scraper import MyInvestorScraper
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

app = Flask(__name__)
CORS(app)
port = os.environ.get("WEB_PORT", 8080)

mongo_user = os.environ["MONGO_USERNAME"]
mongo_password = os.environ["MONGO_PASSWORD"]
mongo_host = os.environ["MONGO_HOST"]
mongo_port = os.environ.get("MONGO_PORT", 27017)
mongo_db_name = "bank_data_db"
mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}"

mongo_client = MongoClient(mongo_uri)

update_cooldown = os.environ.get("UPDATE_COOLDOWN", 60)
config_path = os.environ.get("CONFIG_PATH", "config.yml")

config_loader = ConfigLoader(config_path)
config_loader.check_or_create_default_config()

entity_scrapers = {
    Entity.MY_INVESTOR: MyInvestorScraper(),
    Entity.TRADE_REPUBLIC: TradeRepublicScraper(),
    Entity.UNICAJA: UnicajaScraper(),
    Entity.URBANITAE: UrbanitaeScraper(),
    Entity.WECITY: WecityScraper(),
    Entity.SEGO: SegoScraper()
}
virtual_scraper = SheetsImporter()
position_repository = PositionRepository(client=mongo_client, db_name=mongo_db_name)
auto_contrib_repository = AutoContributionsRepository(client=mongo_client, db_name=mongo_db_name)
transaction_repository = TransactionRepository(client=mongo_client, db_name=mongo_db_name)

get_available_sources = GetAvailableSourcesImpl(config_loader)
scrape = ScrapeImpl(
    update_cooldown,
    position_repository,
    auto_contrib_repository,
    transaction_repository,
    entity_scrapers,
    config_loader)
update_sheets = UpdateSheetsImpl(
    position_repository,
    auto_contrib_repository,
    transaction_repository,
    SheetsExporter(),
    config_loader)
virtual_scrape = VirtualScrapeImpl(
    position_repository,
    transaction_repository,
    virtual_scraper,
    config_loader)
controllers = Controllers(get_available_sources, scrape, update_sheets, virtual_scrape)

app.add_url_rule('/api/v1/scrape', view_func=controllers.get_available_sources, methods=['GET'])
app.add_url_rule('/api/v1/scrape', view_func=controllers.scrape, methods=['POST'])
app.add_url_rule('/api/v1/scrape/virtual', view_func=controllers.virtual_scrape, methods=['POST'])
app.add_url_rule('/api/v1/update-sheets', view_func=controllers.update_sheets, methods=['POST'])

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=port)
