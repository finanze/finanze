import abc

from domain.historic import Historic, HistoricQueryRequest


class GetHistoric(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, query: HistoricQueryRequest) -> Historic:
        pass
