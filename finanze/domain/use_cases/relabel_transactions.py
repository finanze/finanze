import abc

from domain.labeling import RelabelRequest, RelabelResult


class RelabelTransactions(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: RelabelRequest) -> RelabelResult:
        raise NotImplementedError
