from application.ports.position_port import PositionPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_scraper import VirtualScraper
from domain.global_position import SourceType
from domain.scrap_result import ScrapResult, ScrapResultCode
from domain.scraped_data import VirtuallyScrapedData
from domain.use_cases.virtual_scrape import VirtualScrape


class VirtualScrapeImpl(VirtualScrape):

    def __init__(self,
                 position_port: PositionPort,
                 transaction_port: TransactionPort,
                 virtual_scraper: VirtualScraper):
        self.position_port = position_port
        self.transaction_port = transaction_port
        self.virtual_scraper = virtual_scraper

    async def execute(self) -> ScrapResult:
        registered_txs = self.transaction_port.get_ids_by_source_type(SourceType.VIRTUAL)

        global_positions = await self.virtual_scraper.global_positions()
        transactions = await self.virtual_scraper.transactions(registered_txs)

        if global_positions:
            for entity, position in global_positions.items():
                self.position_port.save(entity, position)

        if transactions:
            self.transaction_port.save(transactions)

        data = VirtuallyScrapedData(positions=global_positions, transactions=transactions)

        return ScrapResult(ScrapResultCode.COMPLETED, data=data)
