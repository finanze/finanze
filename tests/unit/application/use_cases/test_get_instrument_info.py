from unittest.mock import AsyncMock

import pytest

from application.use_cases.get_instrument_info import GetInstrumentInfoImpl
from domain.dezimal import Dezimal
from domain.instrument import InstrumentDataRequest, InstrumentInfo, InstrumentType


def _make_info(name: str) -> InstrumentInfo:
    return InstrumentInfo(
        name=name,
        currency="EUR",
        type=InstrumentType.ETF,
        price=Dezimal("10.00"),
    )


@pytest.mark.asyncio
async def test_execute_resolves_issuer_from_instrument_name():
    provider = AsyncMock()
    info = _make_info("Vanguard FTSE All-World ETF")
    provider.get_info.return_value = info
    request = InstrumentDataRequest(type=InstrumentType.ETF, name=info.name)

    result = await GetInstrumentInfoImpl(provider).execute(request)

    assert result is info
    assert result.issuer == "Vanguard"
    provider.get_info.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_execute_returns_none_issuer_for_unknown_instrument_name():
    provider = AsyncMock()
    info = _make_info("Mystery Capital Fund")
    provider.get_info.return_value = info

    result = await GetInstrumentInfoImpl(provider).execute(
        InstrumentDataRequest(type=InstrumentType.MUTUAL_FUND, name=info.name)
    )

    assert result is info
    assert result.issuer is None


@pytest.mark.asyncio
async def test_execute_returns_none_when_provider_finds_no_instrument():
    provider = AsyncMock()
    provider.get_info.return_value = None
    request = InstrumentDataRequest(type=InstrumentType.STOCK, ticker="AAPL")

    result = await GetInstrumentInfoImpl(provider).execute(request)

    assert result is None
    provider.get_info.assert_awaited_once_with(request)
