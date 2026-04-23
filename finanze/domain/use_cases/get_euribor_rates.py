import abc

from domain.euribor import EuriborHistory


class GetEuriborRates(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> EuriborHistory:
        pass
