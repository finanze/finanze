from domain.earnings_expenses import (
    FlowSortField,
    FlowStatus,
    FlowType,
    PendingFlow,
    PendingFlowPage,
    PendingFlowQuery,
    SortOrder,
)
from domain.use_cases.query_pending_flows import QueryPendingFlows
from quart import jsonify, request


def _serialize_flow(flow: PendingFlow) -> dict:
    return {
        "id": str(flow.id),
        "name": flow.name,
        "amount": flow.amount,
        "currency": flow.currency,
        "flow_type": flow.flow_type.value,
        "category": flow.category,
        "status": flow.status.value,
        "status_changed_at": flow.status_changed_at.isoformat()
        if flow.status_changed_at
        else None,
        "date": flow.date.isoformat() if flow.date else None,
        "icon": flow.icon,
    }


def _serialize_page(page: PendingFlowPage) -> dict:
    result = {
        "entries": [_serialize_flow(flow) for flow in page.entries],
        "total": page.total,
        "page": page.page,
        "limit": page.limit,
        "has_more": page.has_more,
        "categories": page.categories,
        "stats": None,
    }

    if page.stats is not None:
        result["stats"] = {
            "earning": {
                "totals": page.stats.earning.totals,
                "count": page.stats.earning.count,
                "by_category": [
                    {
                        "category": stat.category,
                        "name": stat.name,
                        "amounts": stat.amounts,
                    }
                    for stat in page.stats.earning.by_category
                ],
            },
            "expense": {
                "totals": page.stats.expense.totals,
                "count": page.stats.expense.count,
                "by_category": [
                    {
                        "category": stat.category,
                        "name": stat.name,
                        "amounts": stat.amounts,
                    }
                    for stat in page.stats.expense.by_category
                ],
            },
        }

    return result


async def get_pending_flows(query_pending_flows_uc: QueryPendingFlows):
    args = request.args

    try:
        statuses = [FlowStatus(s) for s in args.getlist("status")] or None

        flow_type = args.get("flow_type")
        flow_type = FlowType(flow_type) if flow_type else None

        categories = args.getlist("category") or None

        sort_by = args.get("sort_by")
        sort_by = FlowSortField(sort_by) if sort_by else FlowSortField.AMOUNT

        order = args.get("order")
        order = SortOrder(order) if order else SortOrder.DESC

        page = args.get("page", type=int)
        limit = args.get("limit", type=int)
    except (ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    include_stats = args.get("stats", "false").lower() == "true"
    include_categories = args.get("categories", "false").lower() == "true"

    query = PendingFlowQuery(
        statuses=statuses,
        flow_type=flow_type,
        categories=categories,
        sort_by=sort_by,
        order=order,
        page=page,
        limit=limit,
        include_stats=include_stats,
        include_categories=include_categories,
    )

    result = await query_pending_flows_uc.execute(query)
    return jsonify(_serialize_page(result)), 200
