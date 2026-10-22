import abc

from domain.local_model import ImportedLocalModel


class LocalModelImports(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def folder(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    async def list(self) -> list[ImportedLocalModel]:
        raise NotImplementedError

    @abc.abstractmethod
    async def add(self, path: str) -> ImportedLocalModel:
        raise NotImplementedError

    @abc.abstractmethod
    async def remove(self, model_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def sync(self):
        raise NotImplementedError
