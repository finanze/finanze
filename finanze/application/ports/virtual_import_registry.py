import abc

from domain.virtual_scrape import VirtualDataImport


class VirtualImportRegistry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def insert(self, entry: VirtualDataImport):
        raise NotImplementedError
