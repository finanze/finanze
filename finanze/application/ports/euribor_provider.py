import abc

from domain.euribor import EuriborHistory


class EuriborProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_yearly_euribor_rates(self) -> EuriborHistory:
        raise NotImplementedError
