import abc
from typing import Generator


class TransactionHandlerPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def start(self) -> Generator[None, None, None]:
        raise NotImplementedError
