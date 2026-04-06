import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from infrastructure.controller.config import quart
from infrastructure.controller.routes.get_euribor_rates import get_euribor_rates
from infrastructure.controller.exception_handler import register_exception_handlers

from application.ports.euribor_provider import EuriborProvider
from application.use_cases.get_euribor_rates import GetEuriborRatesImpl
from domain.dezimal import Dezimal
from domain.euribor import EuriborHistory, EuriborRate


EURIBOR_URL = "/api/v1/rates/euribor"


def _sample_history() -> EuriborHistory:
    return EuriborHistory(
        rates=[
            EuriborRate(period="2026-03", rate=Dezimal("2.565")),
            EuriborRate(period="2026-02", rate=Dezimal("2.221")),
            EuriborRate(period="2026-01", rate=Dezimal("2.267")),
            EuriborRate(period="2025-12", rate=Dezimal("2.245")),
            EuriborRate(period="2025-11", rate=Dezimal("2.217")),
            EuriborRate(period="2025-10", rate=Dezimal("2.187")),
            EuriborRate(period="2025-09", rate=Dezimal("2.172")),
            EuriborRate(period="2025-08", rate=Dezimal("2.114")),
            EuriborRate(period="2025-07", rate=Dezimal("2.079")),
            EuriborRate(period="2025-06", rate=Dezimal("2.081")),
            EuriborRate(period="2025-05", rate=Dezimal("2.081")),
            EuriborRate(period="2025-04", rate=Dezimal("2.143")),
        ]
    )


@pytest_asyncio.fixture
async def app(tmp_path):
    euribor_provider = AsyncMock(spec=EuriborProvider)
    euribor_provider.get_yearly_euribor_rates.return_value = _sample_history()
    get_euribor_rates_uc = GetEuriborRatesImpl(euribor_provider)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    test_app = quart(static_dir)
    register_exception_handlers(test_app)

    @test_app.route(EURIBOR_URL, methods=["GET"])
    async def euribor_rates_route():
        return await get_euribor_rates(get_euribor_rates_uc)

    yield test_app, euribor_provider


@pytest_asyncio.fixture
async def client(app):
    test_app, *_ = app
    async with test_app.test_client() as c:
        yield c


class TestGetEuriborRatesEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(self, client):
        response = await client.get(EURIBOR_URL)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_rates_list(self, client):
        response = await client.get(EURIBOR_URL)
        body = await response.get_json()
        assert "rates" in body
        assert isinstance(body["rates"], list)
        assert len(body["rates"]) == 12

    @pytest.mark.asyncio
    async def test_rates_have_period_and_rate(self, client):
        response = await client.get(EURIBOR_URL)
        body = await response.get_json()
        first = body["rates"][0]
        assert "period" in first
        assert "rate" in first
        assert first["period"] == "2026-03"
        assert first["rate"] == pytest.approx(2.565)

    @pytest.mark.asyncio
    async def test_rates_ordered_newest_first(self, client):
        response = await client.get(EURIBOR_URL)
        body = await response.get_json()
        periods = [r["period"] for r in body["rates"]]
        assert periods == sorted(periods, reverse=True)

    @pytest.mark.asyncio
    async def test_empty_rates_when_provider_returns_empty(self, app):
        test_app, provider = app
        provider.get_yearly_euribor_rates.return_value = EuriborHistory()
        async with test_app.test_client() as c:
            response = await c.get(EURIBOR_URL)
            body = await response.get_json()
            assert body["rates"] == []
