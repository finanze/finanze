import abc
from typing import Optional

from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.transactions import Transactions


class VirtualScraper(metaclass=abc.ABCMeta):

    async def global_positions(self,
                               investment_sheets,
                               existing_entities: dict[str, FinancialEntity]) \
            -> tuple[list[GlobalPosition], set[FinancialEntity]]:
        raise NotImplementedError

    async def transactions(self,
                           txs_sheets,
                           registered_txs: set[str],
                           existing_entities: dict[str, FinancialEntity]) \
            -> tuple[Optional[Transactions], set[FinancialEntity]]:
        raise NotImplementedError
