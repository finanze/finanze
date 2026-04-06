import pytest

from unittest.mock import AsyncMock

from application.use_cases.get_euribor_rates import GetEuriborRatesImpl
from application.ports.euribor_provider import EuriborProvider
from domain.dezimal import Dezimal
from domain.euribor import EuriborHistory, EuriborRate


def _history() -> EuriborHistory:
    return EuriborHistory(
        rates=[
            EuriborRate(period="2026-03", rate=Dezimal("2.565")),
            EuriborRate(period="2026-02", rate=Dezimal("2.221")),
        ]
    )


class TestGetEuriborRatesImpl:
    @pytest.mark.asyncio
    async def test_delegates_to_provider(self):
        provider = AsyncMock(spec=EuriborProvider)
        provider.get_yearly_euribor_rates.return_value = _history()

        uc = GetEuriborRatesImpl(provider)
        result = await uc.execute()

        provider.get_yearly_euribor_rates.assert_called_once()
        assert len(result.rates) == 2
        assert result.rates[0].period == "2026-03"
        assert result.rates[0].rate == Dezimal("2.565")

    @pytest.mark.asyncio
    async def test_returns_empty_history_from_provider(self):
        provider = AsyncMock(spec=EuriborProvider)
        provider.get_yearly_euribor_rates.return_value = EuriborHistory()

        uc = GetEuriborRatesImpl(provider)
        result = await uc.execute()

        assert result.rates == []
