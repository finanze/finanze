import abc

from domain.historic import Historic, BaseHistoricEntry


class HistoricPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entries: list[BaseHistoricEntry]):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Historic:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_entity(self, entity_id: int):
        raise NotImplementedError
