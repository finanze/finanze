from application.ports.config_port import ConfigPort
from application.ports.position_port import PositionPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_scraper import VirtualScraper
from application.use_cases.update_sheets import apply_global_config
from domain.global_position import SourceType
from domain.scrap_result import ScrapResult, ScrapResultCode
from domain.scraped_data import VirtuallyScrapedData
from domain.use_cases.virtual_scrape import VirtualScrape


class VirtualScrapeImpl(VirtualScrape):

    def __init__(self,
                 position_port: PositionPort,
                 transaction_port: TransactionPort,
                 virtual_scraper: VirtualScraper,
                 config_port: ConfigPort):
        self.position_port = position_port
        self.transaction_port = transaction_port
        self.virtual_scraper = virtual_scraper
        self.config_port = config_port

    async def execute(self) -> ScrapResult:
        config = self.config_port.load()
        virtual_scrape_config = config["scrape"]["virtual"]

        if not virtual_scrape_config["enabled"]:
            return ScrapResult(ScrapResultCode.DISABLED)

        config_globals = virtual_scrape_config["globals"]

        registered_txs = self.transaction_port.get_ids_by_source_type(SourceType.VIRTUAL)

        investment_sheets = virtual_scrape_config["investments"]
        transaction_sheets = virtual_scrape_config["transactions"]
        apply_global_config(config_globals, investment_sheets)
        apply_global_config(config_globals, transaction_sheets)

        global_positions = await self.virtual_scraper.global_positions(investment_sheets)
        transactions = await self.virtual_scraper.transactions(transaction_sheets, registered_txs)

        if global_positions:
            for entity, position in global_positions.items():
                self.position_port.save(entity, position)

        if transactions:
            self.transaction_port.save(transactions)

        data = VirtuallyScrapedData(positions=global_positions, transactions=transactions)

        return ScrapResult(ScrapResultCode.COMPLETED, data=data)
