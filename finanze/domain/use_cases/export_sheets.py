import abc


class ExportSheets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self):
        raise NotImplementedError
