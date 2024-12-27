import os
from datetime import datetime, timezone

from dateutil.tz import tzlocal

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.config_port import ConfigPort
from application.ports.entity_scraper import EntityScraper
from application.ports.position_port import PositionPort
from application.ports.transaction_port import TransactionPort
from domain.financial_entity import Entity, Feature
from domain.scrap_result import ScrapResultCode, ScrapResult
from domain.scraped_data import ScrapedData
from domain.use_cases.scrape import Scrape

DEFAULT_FEATURES = [Feature.POSITION]


class ScrapeImpl(Scrape):
    def __init__(self,
                 update_cooldown: int,
                 position_port: PositionPort,
                 auto_contr_port: AutoContributionsPort,
                 transaction_port: TransactionPort,
                 entity_scrapers: dict[Entity, EntityScraper],
                 config_port: ConfigPort):
        self.update_cooldown = update_cooldown
        self.position_port = position_port
        self.auto_contr_repository = auto_contr_port
        self.transaction_port = transaction_port
        self.entity_scrapers = entity_scrapers
        self.config_port = config_port

    @staticmethod
    def get_creds(entity: Entity) -> tuple:
        if entity == Entity.MY_INVESTOR:
            return os.environ["MYI_USERNAME"], os.environ["MYI_PASSWORD"]

        elif entity == Entity.TRADE_REPUBLIC:
            return os.environ["TR_PHONE"], os.environ["TR_PIN"]

        elif entity == Entity.UNICAJA:
            return os.environ["UNICAJA_USERNAME"], os.environ["UNICAJA_PASSWORD"]

        elif entity == Entity.URBANITAE:
            return os.environ["URBANITAE_USERNAME"], os.environ["URBANITAE_PASSWORD"]

        elif entity == Entity.WECITY:
            return os.environ["WECITY_USERNAME"], os.environ["WECITY_PASSWORD"]

        elif entity == Entity.SEGO:
            return os.environ["SEGO_USERNAME"], os.environ["SEGO_PASSWORD"]

    async def execute(self,
                      entity: Entity,
                      features: list[Feature],
                      **kwargs) -> ScrapResult:
        scrape_config = self.config_port.load()["scrape"].get("enabledEntities")
        if scrape_config and entity not in scrape_config:
            return ScrapResult(ScrapResultCode.DISABLED)

        if Feature.POSITION in features:
            last_update = self.position_port.get_last_updated(entity)
            if last_update and (datetime.now(timezone.utc) - last_update).seconds < self.update_cooldown:
                remaining_seconds = self.update_cooldown - (datetime.now(timezone.utc) - last_update).seconds
                details = {"lastUpdate": last_update.astimezone(tzlocal()).isoformat(), "wait": remaining_seconds}
                return ScrapResult(ScrapResultCode.COOLDOWN, details=details)

        login_args = kwargs.get("login", {})
        credentials = self.get_creds(entity)

        specific_scraper = self.entity_scrapers[entity]
        login_result = specific_scraper.login(credentials, **login_args)

        if login_result:
            if login_result.get("success", False):
                return ScrapResult(ScrapResultCode.CODE_REQUESTED, details=login_result)
            else:
                return ScrapResult(ScrapResultCode.NOT_LOGGED)

        if not features:
            features = DEFAULT_FEATURES

        position = None
        if Feature.POSITION in features:
            position = await specific_scraper.global_position()

        auto_contributions = None
        if Feature.AUTO_CONTRIBUTIONS in features:
            auto_contributions = await specific_scraper.auto_contributions()

        transactions = None
        if Feature.TRANSACTIONS in features:
            registered_txs = self.transaction_port.get_ids_by_entity(entity.name)
            transactions = await specific_scraper.transactions(registered_txs)

        if position:
            self.position_port.save(entity.name, position)

        if auto_contributions:
            self.auto_contr_repository.save(entity.name, auto_contributions)

        if transactions:
            self.transaction_port.save(transactions)

        data = ScrapedData(position=position, autoContributions=auto_contributions, transactions=transactions)

        return ScrapResult(ScrapResultCode.COMPLETED, data=data)
