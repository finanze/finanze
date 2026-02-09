import abc

from domain.platform import OS
from domain.status import BackendDetails


class ServerDetailsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_backend_details(self) -> BackendDetails:
        raise NotImplementedError

    @abc.abstractmethod
    def get_os(self) -> OS:
        raise NotImplementedError
