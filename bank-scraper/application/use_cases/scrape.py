import os

from application.ports.bank_data_port import BankDataPort
from application.ports.bank_scraper import BankScraper
from domain.bank import Bank
from domain.scrap_result import ScrapResultCode, ScrapResult
from domain.use_cases.scrape import Scrape


class ScrapeImpl(Scrape):
    def __init__(self, bank_data_port: BankDataPort, bank_scrapers: dict[Bank, BankScraper]):
        self.repository = bank_data_port
        self.bank_scrapers = bank_scrapers

    @staticmethod
    def get_creds(bank: Bank) -> tuple:
        if bank == Bank.MY_INVESTOR:
            return os.environ["MYI_USERNAME"], os.environ["MYI_PASSWORD"]

        elif bank == Bank.TRADE_REPUBLIC:
            return os.environ["TR_PHONE"], os.environ["TR_PIN"]

        elif bank == Bank.UNICAJA:
            return os.environ["UNICAJA_USERNAME"], os.environ["UNICAJA_PASSWORD"]

    async def execute(self, bank: Bank, params: dict) -> ScrapResult:
        credentials = self.get_creds(bank)

        summary_generator = self.bank_scrapers[bank]
        login_result = summary_generator.login(credentials, params)

        if login_result:
            return ScrapResult(ScrapResultCode.CODE_REQUESTED, details=login_result)

        result = await summary_generator.generate()

        if result.code == ScrapResultCode.COMPLETED:
            self.repository.upsert_bank_data(bank, result.data)

        return result
