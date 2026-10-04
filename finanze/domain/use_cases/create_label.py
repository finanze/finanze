import abc

from domain.labeling import Label


class CreateLabel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, label: Label) -> Label:
        raise NotImplementedError
