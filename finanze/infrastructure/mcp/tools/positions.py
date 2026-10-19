from typing import Annotated, Optional

from domain.auto_contributions import ContributionQueryRequest
from domain.gains_timeline import GainsAssetFilter, GainsTimelineQuery
from domain.global_position import PositionQueryRequest, ProductType
from domain.historic import HistoricQueryRequest, HistoricSortBy, SortOrder
from domain.networth_summary import NetworthSummaryQuery
from domain.networth_timeline import NetworthTimelineQuery
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.tools.common import (
    CurrencyCode,
    EntityIds,
    FromDate,
    Granularity,
    Page,
    PointsGranularity,
    ProductTypes,
    ToDate,
    resolve_currency,
    sample,
)
from infrastructure.mcp.use_cases import McpUseCases

RealFilter = Annotated[
    Optional[bool],
    Field(
        description="true: only data fetched from entities, false: only manually added or imported data. Omit for both."
    ),
]


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("Get net worth")
    async def get_net_worth(currency: CurrencyCode = None):
        """Get the current total net worth and its breakdown by asset bucket (product types, plus REAL_ESTATE and REAL_ESTATE_RESIDENCE), converted to one currency. Loans and credits are subtracted."""
        base_currency = await resolve_currency(ucs, currency)
        return await ucs.get_networth_summary.execute(
            NetworthSummaryQuery(base_currency=base_currency)
        )

    @registry.read("Get positions")
    async def get_positions(
        entities: EntityIds = None,
        product_types: ProductTypes = None,
        real: RealFilter = None,
    ):
        """Get the detailed current positions (accounts, cards, loans, stocks/ETFs, funds, deposits, crypto, commodities, etc.) grouped by entity ID, in their original currencies."""
        return await ucs.get_position.execute(
            PositionQueryRequest(entities=entities, products=product_types, real=real)
        )

    @registry.read("Get periodic contributions")
    async def get_contributions(entities: EntityIds = None, real: RealFilter = None):
        """Get the periodic automatic contributions (recurring investment orders, e.g. monthly fund or ETF purchases) grouped by entity ID."""
        return await ucs.get_contributions.execute(
            ContributionQueryRequest(entities=entities, real=real)
        )

    @registry.read("Get historic positions")
    async def get_historic_positions(
        entities: EntityIds = None,
        product_types: ProductTypes = None,
        page: Page = 1,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
        sort_by: HistoricSortBy = HistoricSortBy.MATURITY,
        sort_order: SortOrder = SortOrder.DESC,
    ):
        """Get past completed Real Estate Crowdfunding and Factoring investments with invested amounts, returns, and related transactions."""
        return await ucs.get_historic.execute(
            HistoricQueryRequest(
                entities=entities,
                product_types=product_types,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )

    @registry.read("Get net worth timeline")
    async def get_net_worth_timeline(
        currency: CurrencyCode = None,
        from_date: FromDate = None,
        to_date: ToDate = None,
        granularity: PointsGranularity = Granularity.MONTH,
    ):
        """Get the historical net worth evolution, with total and breakdown by asset bucket per point."""
        base_currency = await resolve_currency(ucs, currency)
        timeline = await ucs.get_networth_timeline.execute(
            NetworthTimelineQuery(
                base_currency=base_currency, from_date=from_date, to_date=to_date
            )
        )
        return {
            "currency": timeline.currency,
            "points": sample(timeline.points, granularity, lambda p: p.date),
        }

    @registry.read("Get gains timeline")
    async def get_gains_timeline(
        product_types: Annotated[
            list[ProductType],
            Field(
                description="Investment product types to analyze, e.g. STOCK_ETF, FUND, CRYPTO.",
                min_length=1,
            ),
        ],
        currency: CurrencyCode = None,
        entities: EntityIds = None,
        from_date: FromDate = None,
        to_date: ToDate = None,
        granularity: PointsGranularity = Granularity.MONTH,
        include_breakdown: Annotated[
            bool, Field(description="Include per asset metrics in each point.")
        ] = False,
    ):
        """Get investment performance over time: value, cost basis, net contributions, gain, period return and index per point, plus XIRR and data quality warnings."""
        base_currency = await resolve_currency(ucs, currency)
        timeline = await ucs.get_gains_timeline.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=p) for p in product_types],
                base_currency=base_currency,
                entities=entities,
                from_date=from_date,
                to_date=to_date,
            )
        )
        points = sample(timeline.points, granularity, lambda p: p.date)
        if not include_breakdown:
            points = [
                {"date": p.date, "metrics": p.metrics, "estimated": p.estimated}
                for p in points
            ]
        return {
            "currency": timeline.currency,
            "method": timeline.method,
            "basis": timeline.basis,
            "quality": timeline.quality,
            "basis_status": timeline.basis_status,
            "xirr": timeline.xirr,
            "annualized_xirr": timeline.annualized_xirr,
            "opening_value": timeline.opening_value,
            "warnings": timeline.warnings,
            "not_applicable_reasons": timeline.not_applicable_reasons,
            "points": points,
        }
