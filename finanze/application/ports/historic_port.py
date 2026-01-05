import abc
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
    async def delete_by_entity(self, entity_id: UUID):
        raise NotImplementedError
