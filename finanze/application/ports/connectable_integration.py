import abc
from typing import Generic, TypeVar

T = TypeVar("T")


class ConnectableIntegration(Generic[T], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def setup(self, credentials: T):
        raise NotImplementedError
