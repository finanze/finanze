import os
from datetime import datetime, timezone

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.bank_data_port import BankDataPort
from application.ports.bank_scraper import BankScraper
from domain.bank import Bank
from domain.scrap_result import ScrapResultCode, ScrapResult
from domain.use_cases.scrape import Scrape


class ScrapeImpl(Scrape):
    def __init__(self,
                 update_cooldown: int,
                 bank_data_port: BankDataPort,
                 auto_contr_port: AutoContributionsPort,
                 bank_scrapers: dict[Bank, BankScraper]):
        self.update_cooldown = update_cooldown
        self.bank_data_port = bank_data_port
        self.auto_contr_repository = auto_contr_port
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
        last_update = self.bank_data_port.get_last_updated(bank)
        if last_update and (datetime.now(timezone.utc) - last_update).seconds < self.update_cooldown:
            remaining_seconds = self.update_cooldown - (datetime.now(timezone.utc) - last_update).seconds
            return ScrapResult(ScrapResultCode.COOLDOWN,
                               details={"lastUpdate": last_update.isoformat(), "wait": remaining_seconds})

        credentials = self.get_creds(bank)

        summary_generator = self.bank_scrapers[bank]
        login_result = summary_generator.login(credentials, params)

        if login_result:
            return ScrapResult(ScrapResultCode.CODE_REQUESTED, details=login_result)

        result = await summary_generator.generate()

        if result.code == ScrapResultCode.COMPLETED:
            if result.data.position:
                self.bank_data_port.insert(bank, result.data.position)

            if result.data.autoContributions:
                self.auto_contr_repository.upsert(bank, result.data.autoContributions)

        return result
