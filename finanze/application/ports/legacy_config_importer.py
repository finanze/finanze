import abc


class LegacyConfigImporter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def import_data(self, data: bytes):
        raise NotImplementedError
