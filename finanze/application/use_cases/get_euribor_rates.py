from application.ports.euribor_provider import EuriborProvider
from domain.euribor import EuriborHistory
from domain.use_cases.get_euribor_rates import GetEuriborRates


class GetEuriborRatesImpl(GetEuriborRates):
    def __init__(self, euribor_provider: EuriborProvider):
        self._euribor_provider = euribor_provider

    async def execute(self) -> EuriborHistory:
        return await self._euribor_provider.get_yearly_euribor_rates()
