import logging
import os

from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient
from waitress import serve

from application.use_cases.fiscal_year import FiscalYearImpl
from application.use_cases.scrape import ScrapeImpl
from application.use_cases.update_sheets import UpdateSheetsImpl
from domain.bank import Bank
from infrastructure.controller.controllers import Controllers
from infrastructure.repository.auto_contributions_repository import AutoContributionsRepository
from infrastructure.repository.bank_data_repository import BankDataRepository
from infrastructure.repository.transaction_repository import TransactionRepository
from infrastructure.scrapers.myinvestor_scraper import MyInvestorScraper
from infrastructure.scrapers.trade_republic_scraper import TradeRepublicScraper
from infrastructure.scrapers.unicaja_scraper import UnicajaScraper
from infrastructure.scrapers.urbanitae_scraper import UrbanitaeScraper
from infrastructure.scrapers.wecity_scraper import WecityScraper
from infrastructure.sheets_exporter.sheets_exporter import SheetsExporter

log_level = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

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

bank_scrapers = {
    Bank.MY_INVESTOR: MyInvestorScraper(),
    Bank.TRADE_REPUBLIC: TradeRepublicScraper(),
    Bank.UNICAJA: UnicajaScraper(),
    Bank.URBANITAE: UrbanitaeScraper(),
    Bank.WECITY: WecityScraper(),
}
bank_data_repository = BankDataRepository(client=mongo_client, db_name=mongo_db_name)
auto_contrib_repository = AutoContributionsRepository(client=mongo_client, db_name=mongo_db_name)
transaction_repository = TransactionRepository(client=mongo_client, db_name=mongo_db_name)
scrape = ScrapeImpl(
    update_cooldown,
    bank_data_repository,
    auto_contrib_repository,
    transaction_repository,
    bank_scrapers)
update_sheets = UpdateSheetsImpl(
    bank_data_repository,
    auto_contrib_repository,
    transaction_repository,
    SheetsExporter())
fiscal_year = FiscalYearImpl(transaction_repository)
controllers = Controllers(scrape, update_sheets, fiscal_year)

app.add_url_rule('/api/v1/scrape', view_func=controllers.scrape, methods=['POST'])
app.add_url_rule('/api/v1/update-sheets', view_func=controllers.update_sheets, methods=['POST'])
app.add_url_rule('/api/v1/calculations/year', view_func=controllers.calc_fiscal_year, methods=['POST'])

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=port)
