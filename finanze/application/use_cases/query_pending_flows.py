from application.ports.pending_flow_port import PendingFlowPort
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    CategoryStat,
    FlowSortField,
    FlowStatus,
    FlowType,
    FlowTypeStat,
    PendingFlow,
    PendingFlowPage,
    PendingFlowQuery,
    PendingFlowStats,
    SortOrder,
)
from domain.use_cases.query_pending_flows import QueryPendingFlows


class QueryPendingFlowsImpl(QueryPendingFlows):
    def __init__(self, pending_flow_port: PendingFlowPort):
        self._pending_flow_port = pending_flow_port

    async def execute(self, query: PendingFlowQuery) -> PendingFlowPage:
        flows = await self._pending_flow_port.get_all()

        filtered = self._filter(
            flows,
            statuses=query.statuses,
            flow_type=query.flow_type,
            categories=query.categories,
        )

        ordered = self._sort(filtered, query.sort_by, query.order)

        total = len(ordered)

        if query.page is not None and query.limit is not None:
            start = (query.page - 1) * query.limit
            end = start + query.limit
            entries = ordered[start:end]
            has_more = end < total
        else:
            entries = ordered
            has_more = False

        stats = None
        if query.include_stats:
            stats = self._build_stats(flows, categories=query.categories)

        categories = None
        if query.include_categories:
            categories = self._build_categories(flows)

        return PendingFlowPage(
            entries=entries,
            total=total,
            page=query.page,
            limit=query.limit,
            has_more=has_more,
            stats=stats,
            categories=categories,
        )

    @staticmethod
    def _filter(
        flows: list[PendingFlow],
        statuses=None,
        flow_type=None,
        categories=None,
    ) -> list[PendingFlow]:
        result = flows
        if statuses:
            status_set = set(statuses)
            result = [f for f in result if f.status in status_set]
        if flow_type is not None:
            result = [f for f in result if f.flow_type == flow_type]
        if categories:
            category_set = set(categories)
            result = [f for f in result if f.category in category_set]
        return result

    @staticmethod
    def _sort(
        flows: list[PendingFlow],
        sort_by: FlowSortField,
        order: SortOrder,
    ) -> list[PendingFlow]:
        reverse = order == SortOrder.DESC
        if sort_by == FlowSortField.DATE:
            with_date = [f for f in flows if f.date is not None]
            without_date = [f for f in flows if f.date is None]
            with_date.sort(key=lambda f: f.date, reverse=reverse)
            return with_date + without_date
        return sorted(flows, key=lambda f: f.amount, reverse=reverse)

    def _build_stats(
        self,
        flows: list[PendingFlow],
        categories=None,
    ) -> PendingFlowStats:
        active = [f for f in flows if f.status == FlowStatus.ACTIVE]
        active = self._filter(active, categories=categories)
        per_entry = bool(categories)

        return PendingFlowStats(
            earning=self._flow_type_stat(active, FlowType.EARNING, per_entry),
            expense=self._flow_type_stat(active, FlowType.EXPENSE, per_entry),
        )

    @staticmethod
    def _flow_type_stat(
        flows: list[PendingFlow], flow_type: FlowType, per_entry: bool = False
    ) -> FlowTypeStat:
        typed = [f for f in flows if f.flow_type == flow_type]

        totals: dict[str, Dezimal] = {}
        by_category: dict = {}
        individual: list[CategoryStat] = []
        for flow in typed:
            totals[flow.currency] = totals.get(flow.currency, Dezimal(0)) + flow.amount
            if per_entry or not flow.category:
                individual.append(
                    CategoryStat(
                        category=flow.category,
                        name=flow.name,
                        amounts={flow.currency: flow.amount},
                    )
                )
            else:
                amounts = by_category.setdefault(flow.category, {})
                amounts[flow.currency] = (
                    amounts.get(flow.currency, Dezimal(0)) + flow.amount
                )

        return FlowTypeStat(
            totals=totals,
            by_category=[
                CategoryStat(category=category, amounts=amounts)
                for category, amounts in by_category.items()
            ]
            + individual,
            count=len(typed),
        )

    def _build_categories(
        self,
        flows: list[PendingFlow],
    ) -> list[str]:
        seen = []
        for flow in flows:
            if flow.category and flow.category not in seen:
                seen.append(flow.category)
        return seen
