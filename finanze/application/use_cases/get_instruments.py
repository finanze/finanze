from typing import List

from application.ports.instrument_info_provider import InstrumentInfoProvider
from domain.instrument import InstrumentDataRequest, InstrumentOverview
from domain.use_cases.get_instruments import GetInstruments


class GetInstrumentsImpl(GetInstruments):
    def __init__(self, provider: InstrumentInfoProvider):
        self._provider = provider

    def execute(self, request: InstrumentDataRequest) -> List[InstrumentOverview]:  # noqa: D401
        return self._provider.lookup(request)
