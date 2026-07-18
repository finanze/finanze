import abc
from typing import List, Optional
from uuid import UUID

from domain.historic import BaseHistoricEntry, Historic, HistoricQueryRequest


class HistoricPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, entries: list[BaseHistoricEntry]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_filters(
        self, query: HistoricQueryRequest, fetch_related_txs: bool = False
    ) -> Historic:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_entity_account_id(self, entity_account_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(
        self, entry_id: UUID, fetch_related_txs: bool = False
    ) -> Optional[BaseHistoricEntry]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_manual_key(
        self, manual_key: str, fetch_related_txs: bool = False
    ) -> Optional[BaseHistoricEntry]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_id(self, entry_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_manual_by_entity(
        self, entity_id: UUID, fetch_related_txs: bool = False
    ) -> List[BaseHistoricEntry]:
        raise NotImplementedError

    @abc.abstractmethod
    async def upsert(self, entry: BaseHistoricEntry):
        raise NotImplementedError

    @abc.abstractmethod
    async def link_txs(self, entry_id: UUID, tx_ids: list[UUID]):
        raise NotImplementedError
