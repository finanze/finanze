import abc

from domain.forecast import ForecastRequest, ForecastResult


class Forecast(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, request: ForecastRequest) -> ForecastResult:
        pass
