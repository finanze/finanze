import abc

from domain.historic import DeleteManualHistoricEntryRequest


class DeleteManualHistoricEntry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: DeleteManualHistoricEntryRequest):
        raise NotImplementedError
