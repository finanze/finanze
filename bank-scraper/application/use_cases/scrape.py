import os
from datetime import datetime, timezone

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.bank_data_port import BankDataPort
from application.ports.bank_scraper import BankScraper
from application.ports.transaction_port import TransactionPort
from domain.bank import Bank, BankFeature
from domain.scrap_result import ScrapResultCode, ScrapResult
from domain.scraped_bank_data import ScrapedBankData
from domain.use_cases.scrape import Scrape

DEFAULT_FEATURES = [BankFeature.POSITION]


class ScrapeImpl(Scrape):
    def __init__(self,
                 update_cooldown: int,
                 bank_data_port: BankDataPort,
                 auto_contr_port: AutoContributionsPort,
                 transaction_port: TransactionPort,
                 bank_scrapers: dict[Bank, BankScraper]):
        self.update_cooldown = update_cooldown
        self.bank_data_port = bank_data_port
        self.auto_contr_repository = auto_contr_port
        self.transaction_port = transaction_port
        self.bank_scrapers = bank_scrapers

    @staticmethod
    def get_creds(bank: Bank) -> tuple:
        if bank == Bank.MY_INVESTOR:
            return os.environ["MYI_USERNAME"], os.environ["MYI_PASSWORD"]

        elif bank == Bank.TRADE_REPUBLIC:
            return os.environ["TR_PHONE"], os.environ["TR_PIN"]

        elif bank == Bank.UNICAJA:
            return os.environ["UNICAJA_USERNAME"], os.environ["UNICAJA_PASSWORD"]

    async def execute(self,
                      bank: Bank,
                      features: list[BankFeature],
                      **kwargs) -> ScrapResult:
        if BankFeature.POSITION in features:
            last_update = self.bank_data_port.get_last_updated(bank)
            if last_update and (datetime.now(timezone.utc) - last_update).seconds < self.update_cooldown:
                remaining_seconds = self.update_cooldown - (datetime.now(timezone.utc) - last_update).seconds
                details = {"lastUpdate": last_update.isoformat(), "wait": remaining_seconds}
                return ScrapResult(ScrapResultCode.COOLDOWN, details=details)

        login_args = kwargs.get("login", {})
        credentials = self.get_creds(bank)

        specific_scraper = self.bank_scrapers[bank]
        login_result = specific_scraper.login(credentials, **login_args)

        if login_result:
            return ScrapResult(ScrapResultCode.CODE_REQUESTED, details=login_result)

        if not features:
            features = DEFAULT_FEATURES

        position = None
        if BankFeature.POSITION in features:
            position = await specific_scraper.global_position()

        auto_contributions = None
        if BankFeature.AUTO_CONTRIBUTIONS in features:
            auto_contributions = await specific_scraper.auto_contributions()

        transactions = None
        if BankFeature.TRANSACTIONS in features:
            registered_txs = self.transaction_port.get_ids_by_source(bank)
            transactions = await specific_scraper.transactions(registered_txs)

        if position:
            self.bank_data_port.save(bank, position)

        if auto_contributions:
            self.auto_contr_repository.save(bank, auto_contributions)

        if transactions:
            self.transaction_port.save(bank, transactions)

        data = ScrapedBankData(position=position, autoContributions=auto_contributions, transactions=transactions)

        return ScrapResult(ScrapResultCode.COMPLETED, data=data)
