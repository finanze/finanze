import abc

from domain.labeling import Label


class UpdateLabel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, label: Label):
        raise NotImplementedError
