from typing import Optional

from application.ports.instrument_info_provider import InstrumentInfoProvider
from domain.instrument import InstrumentDataRequest, InstrumentInfo
from domain.instrument_issuer import resolve_issuer
from domain.use_cases.get_instrument_info import GetInstrumentInfo


class GetInstrumentInfoImpl(GetInstrumentInfo):
    def __init__(self, provider: InstrumentInfoProvider):
        self._provider = provider

    async def execute(self, request: InstrumentDataRequest) -> Optional[InstrumentInfo]:  # noqa: D401
        info = await self._provider.get_info(request)
        if info is None:
            return None

        info.issuer = resolve_issuer(None, info.name)
        return info
