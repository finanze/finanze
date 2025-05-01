import abc

from domain.data_init import DatasourceInitParams


class DatasourceInitiator(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def initialize(self, params: DatasourceInitParams):
        raise NotImplementedError
