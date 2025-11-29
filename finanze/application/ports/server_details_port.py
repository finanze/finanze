import abc

from domain.status import BackendDetails


class ServerDetailsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_backend_details(self) -> BackendDetails:
        raise NotImplementedError
