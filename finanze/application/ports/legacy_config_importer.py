import abc
from warnings import deprecated


@deprecated(
    "Only for importing legacy config backups; use current settings APIs for new data.",
    category=None,
)
class LegacyConfigImporter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def import_data(self, data: bytes):
        raise NotImplementedError
