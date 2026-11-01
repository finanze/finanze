import abc

from domain.labeling import UpdateTransactionLabelsRequest


class UpdateTransactionLabels(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: UpdateTransactionLabelsRequest):
        raise NotImplementedError
