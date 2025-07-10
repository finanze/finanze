import abc

from domain.virtual_fetch import VirtualDataImport


class VirtualImportRegistry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, entries: list[VirtualDataImport]):
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_import_records(self) -> list[VirtualDataImport]:
        raise NotImplementedError
