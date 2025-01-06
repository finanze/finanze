import abc

from domain.historic import Historic


class HistoricPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, entries: Historic):
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> Historic:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_by_entity(self, entity: str):
        raise NotImplementedError
