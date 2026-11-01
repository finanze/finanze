import abc

from domain.local_model import LocalRouterConnection, LocalRouterModel


class LocalModelRouter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def probe(self, connection: LocalRouterConnection):
        raise NotImplementedError

    @abc.abstractmethod
    async def is_healthy(self, connection: LocalRouterConnection) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def list_models(
        self, connection: LocalRouterConnection, reload: bool = False
    ) -> list[LocalRouterModel]:
        raise NotImplementedError

    @abc.abstractmethod
    async def download(self, connection: LocalRouterConnection, model_id: str):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, connection: LocalRouterConnection, model_id: str):
        raise NotImplementedError

    @abc.abstractmethod
    async def load(self, connection: LocalRouterConnection, model_id: str):
        raise NotImplementedError

    @abc.abstractmethod
    async def unload(self, connection: LocalRouterConnection, model_id: str):
        raise NotImplementedError
