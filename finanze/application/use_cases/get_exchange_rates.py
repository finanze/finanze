from application.ports.exchange_rate_provider import ExchangeRateProvider
from domain.exchange_rate import ExchangeRates
from domain.use_cases.get_exchange_rates import GetExchangeRates


class GetExchangeRatesImpl(GetExchangeRates):
    def __init__(self, exchange_rates_provider: ExchangeRateProvider):
        self.exchange_rates_provider = exchange_rates_provider

    def execute(self) -> ExchangeRates:
        return self.exchange_rates_provider.get_matrix()
