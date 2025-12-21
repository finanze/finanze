import abc
from typing import Optional

from domain.data_init import DatasourceInitParams
from domain.user import User


class DatasourceInitiator(metaclass=abc.ABCMeta):
    @property
    def unlocked(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def lock(self):
        raise NotImplementedError

    @abc.abstractmethod
    def initialize(self, params: DatasourceInitParams):
        raise NotImplementedError

    @abc.abstractmethod
    def change_password(self, params: DatasourceInitParams, new_password: str):
        raise NotImplementedError

    @abc.abstractmethod
    def get_hashed_password(self) -> Optional[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_user(self) -> Optional[User]:
        raise NotImplementedError
