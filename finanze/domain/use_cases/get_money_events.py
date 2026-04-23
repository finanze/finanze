import abc

from domain.money_event import MoneyEventQuery, MoneyEvents


class GetMoneyEvents(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, query: MoneyEventQuery) -> MoneyEvents:
        raise NotImplementedError
