import abc

from domain.virtual_fetch import VirtualDataImport


class VirtualImportRegistry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, entry: VirtualDataImport):
        raise NotImplementedError
