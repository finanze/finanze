from unittest.mock import AsyncMock

import pytest

from domain.dezimal import Dezimal
from infrastructure.client.rates.exchange_rate_client import ExchangeRateClient


def _build_client() -> ExchangeRateClient:
    client = ExchangeRateClient()
    client._session = AsyncMock()
    return client


class TestLoadRateMatrix:
    @pytest.mark.asyncio
    async def test_partial_failure_keeps_previous_matrix(self):
        client = _build_client()
        previous = {"EUR": {"BTC": Dezimal("0.00002")}}
        client._rates = previous

        client._fetch_rates = AsyncMock(
            side_effect=[
                {"date": "2026-07-27", "eur": {"btc": 0.00003}},
                RuntimeError("blocked"),
            ]
        )

        with pytest.raises(RuntimeError):
            await client._load_rate_matrix(5)

        assert client._rates == previous

    @pytest.mark.asyncio
    async def test_empty_rate_set_keeps_previous_matrix(self):
        client = _build_client()
        previous = {"EUR": {"BTC": Dezimal("0.00002")}}
        client._rates = previous

        client._fetch_rates = AsyncMock(
            return_value={"date": "2026-07-27", "eur": {}, "usd": {}}
        )

        await client._load_rate_matrix(5)

        assert client._rates == previous

    @pytest.mark.asyncio
    async def test_non_positive_rates_are_dropped(self):
        client = _build_client()

        async def _fetch(currency, request_timeout):
            return {
                "date": "2026-07-27",
                currency.lower(): {"btc": 0, "usd": 1.1, "gbp": "nope"},
            }

        client._fetch_rates = AsyncMock(side_effect=_fetch)

        await client._load_rate_matrix(5)

        assert client._rates["EUR"] == {"USD": Dezimal("1.1")}
