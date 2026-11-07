import abc
from uuid import UUID


class HostIdentityPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_host_id(self) -> UUID:
        raise NotImplementedError
