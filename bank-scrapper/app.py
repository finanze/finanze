import os

from flask import Flask
from waitress import serve

from application.use_cases.scrape import ScrapeImpl
from application.use_cases.update_sheets import UpdateSheetsImpl
from domain.bank import Bank
from infrastructure.controller.controllers import Controllers
from infrastructure.repository.bank_data_repository import BankDataRepository
from infrastructure.scrapers.myinvestor_scraper import MyInvestorSummaryGenerator
from infrastructure.scrapers.trade_republic_scraper import TradeRepublicSummaryGenerator
from infrastructure.scrapers.unicaja_scraper import UnicajaSummaryGenerator
from infrastructure.sheets_exporter.sheets_exporter import SheetsExporter

app = Flask(__name__)
port = os.environ.get("WEB_PORT", 8080)

mongo_user = os.environ["MONGO_USERNAME"]
mongo_password = os.environ["MONGO_PASSWORD"]
mongo_host = os.environ["MONGO_HOST"]
mongo_port = os.environ.get("MONGO_PORT", 27017)
mongo_db_name = "bank_data_db"
mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}"

bank_scrapers = {
    Bank.MY_INVESTOR: MyInvestorSummaryGenerator(),
    Bank.TRADE_REPUBLIC: TradeRepublicSummaryGenerator(),
    Bank.UNICAJA: UnicajaSummaryGenerator(),
}
bank_data_repository = BankDataRepository(uri=mongo_uri, db_name=mongo_db_name)
scraper_service = ScrapeImpl(bank_data_repository, bank_scrapers)
sheet_export_service = UpdateSheetsImpl(bank_data_repository, SheetsExporter())
controllers = Controllers(scraper_service, sheet_export_service)

app.add_url_rule('/api/v1/scrape', view_func=controllers.scrape, methods=['POST'])
app.add_url_rule('/api/v1/update-sheets', view_func=controllers.update_sheets, methods=['POST'])

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=port)
