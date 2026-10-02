from datetime import date
from unittest.mock import AsyncMock

import pytest

from infrastructure.client.entity.financial.urbanitae.urbanitae_fetcher import (
    UrbanitaeFetcher,
)


def _make_fetcher(investment_period, opening_line=None):
    fetcher = UrbanitaeFetcher()
    fetcher._client = AsyncMock()
    fetcher._client.get_project_detail.return_value = {
        "openingLine": opening_line,
        "details": {"investmentPeriod": investment_period},
        "fund": {"apreciationProfitability": "12.5", "fields": []},
    }
    return fetcher


def _investment():
    return {
        "projectId": "P000001",
        "projectName": "Test Project",
        "projectType": "RENT",
        "projectBusinessModel": "COMMERCIAL_OFFICE",
        "projectPhase": "FORMALIZED",
        "investedQuantity": "1000",
        "investedQuantityActive": "1000",
        "lastInvestDate": "2024-02-29T15:00:23.525+0000",
    }


# Raw openingLine fragments as returned by /api/projects/{id} for a rent project
RENT_OPENING_LINE_EN = (
    '<p style="text-align: justify;"><strong>•<span style="white-space: pre;">'
    "\t</span>Ticket: €1,180,000 // Term: 60 months</strong></p>"
    '<p style="text-align: justify;"><strong>•<span style="white-space: pre;">'
    "\t</span>Quarterly interest payment</strong></p>"
)

# Same project with ?lang=es_ES
RENT_OPENING_LINE_ES = (
    '<p class="ql-align-justify"><strong>•\tTicket: 1.180.000€ // '
    "Plazo: 60 meses</strong></p>"
    '<p class="ql-align-justify"><strong>•\tDividendo trimestral</strong></p>'
)


class TestMapInvestmentMaturity:
    @pytest.mark.asyncio
    async def test_single_value_period(self):
        fetcher = _make_fetcher("34")
        result = await fetcher._map_investment(_investment())
        assert result.maturity == date(2026, 12, 29)

    @pytest.mark.asyncio
    async def test_range_period_uses_upper_bound(self):
        fetcher = _make_fetcher("48-54")
        result = await fetcher._map_investment(_investment())
        assert result.maturity == date(2028, 8, 29)

    @pytest.mark.asyncio
    async def test_rent_period_takes_term_from_opening_line(self):
        fetcher = _make_fetcher("Quarterly", RENT_OPENING_LINE_EN)
        result = await fetcher._map_investment(_investment())
        assert result is not None
        assert result.maturity == date(2029, 2, 28)

    @pytest.mark.asyncio
    async def test_rent_period_takes_term_from_spanish_opening_line(self):
        fetcher = _make_fetcher("Trimestral", RENT_OPENING_LINE_ES)
        result = await fetcher._map_investment(_investment())
        assert result is not None
        assert result.maturity == date(2029, 2, 28)

    @pytest.mark.asyncio
    async def test_rent_period_term_in_years(self):
        fetcher = _make_fetcher("Quarterly", "Ticket: €500,000 // Term: 5 years")
        result = await fetcher._map_investment(_investment())
        assert result.maturity == date(2029, 2, 28)

    @pytest.mark.asyncio
    async def test_rent_period_term_with_html_entities(self):
        fetcher = _make_fetcher("Quarterly", "Term:&nbsp;60&nbsp;months")
        result = await fetcher._map_investment(_investment())
        assert result.maturity == date(2029, 2, 28)

    @pytest.mark.asyncio
    async def test_rent_period_term_range_uses_upper_bound(self):
        fetcher = _make_fetcher("Quarterly", "Term: 48-60 months")
        result = await fetcher._map_investment(_investment())
        assert result.maturity == date(2029, 2, 28)

    @pytest.mark.asyncio
    async def test_rent_period_without_term_skips_investment(self):
        fetcher = _make_fetcher("Quarterly", "Rental project with no term")
        result = await fetcher._map_investment(_investment())
        assert result is None

    @pytest.mark.asyncio
    async def test_rent_period_without_opening_line_skips_investment(self):
        fetcher = _make_fetcher("Quarterly")
        result = await fetcher._map_investment(_investment())
        assert result is None
