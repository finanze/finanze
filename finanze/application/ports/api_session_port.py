import abc
from typing import Optional


class ApiSessionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def create(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def is_valid(self, token: Optional[str]) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def revoke_all(self):
        raise NotImplementedError
