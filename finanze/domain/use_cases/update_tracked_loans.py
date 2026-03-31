import abc


class UpdateTrackedLoans(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self):
        raise NotImplementedError
