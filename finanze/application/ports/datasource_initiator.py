import abc

from domain.data_init import DatasourceInitParams


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
