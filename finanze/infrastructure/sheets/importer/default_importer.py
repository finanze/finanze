from typing import Optional

from application.ports.virtual_scraper import VirtualScraper
from domain.exception.exceptions import NoAdapterFound
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.transactions import Transactions


class NullImporter(VirtualScraper):

    async def global_positions(self,
                               investment_configs,
                               existing_entities: dict[str, FinancialEntity]) \
            -> tuple[list[GlobalPosition], set[FinancialEntity]]:
        raise NoAdapterFound("No adapter found for importer, are credentials set up?")

    async def transactions(self,
                           txs_configs,
                           registered_txs: set[str],
                           existing_entities: dict[str, FinancialEntity]) \
            -> tuple[Optional[Transactions], set[FinancialEntity]]:
        raise NoAdapterFound("No adapter found for importer, are credentials set up?")
