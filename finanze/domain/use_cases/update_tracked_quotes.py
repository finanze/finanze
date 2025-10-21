import abc


class UpdateTrackedQuotes(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self):
        raise NotImplementedError
