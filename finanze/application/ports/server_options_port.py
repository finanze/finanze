import abc

from domain.status import BackendOptions


class ServerOptionsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_backend_options(self) -> BackendOptions:
        raise NotImplementedError
