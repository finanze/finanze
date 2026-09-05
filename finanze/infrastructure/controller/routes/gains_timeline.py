from datetime import date
from uuid import UUID

from domain.gains_timeline import (
    FixedIncomeAccrual,
    GainsAssetFilter,
    GainsCalculationMode,
    GainsMetrics,
    GainsTimelineQuery,
)
from domain.global_position import EquityType, ProductType
from domain.use_cases.get_gains_timeline import GetGainsTimeline
from quart import jsonify, request


def _invalid(message: str):
    return jsonify({"code": "INVALID_REQUEST", "message": message}), 400


def _serialize_metrics(metrics: GainsMetrics) -> dict:
    return {
        "value": metrics.value,
        "cost_basis": metrics.cost_basis,
        "net_contributions": metrics.net_contributions,
        "gain": metrics.gain,
        "period_return": metrics.period_return,
        "index": metrics.index,
    }


async def gains_timeline(get_gains_timeline_uc: GetGainsTimeline):
    base_currency = request.args.get("base_currency")
    raw_product_types = request.args.getlist("product_type")
    raw_assets = request.args.getlist("asset")
    portfolio_names = sorted(
        {value for value in request.args.getlist("portfolio") if value}
    )
    raw_equity_types = request.args.getlist("equity_type")
    raw_wallet_ids = request.args.getlist("wallet_id")
    if not base_currency:
        return _invalid("base_currency is required.")
    if not raw_product_types and not raw_assets:
        return _invalid("At least one product_type or asset is required.")

    filters: dict[ProductType, set[str] | None] = {}
    try:
        for raw_product_type in raw_product_types:
            filters[ProductType(raw_product_type)] = None
        for raw_asset in raw_assets:
            product_type_raw, separator, asset_key = raw_asset.partition(":")
            if not separator or not product_type_raw or not asset_key:
                return _invalid("Invalid asset. Use PRODUCT_TYPE:ASSET_KEY.")
            product_type = ProductType(product_type_raw)
            if filters.get(product_type) is None and product_type in filters:
                filters[product_type] = set()
            filters.setdefault(product_type, set()).add(asset_key)
        if portfolio_names and ProductType.FUND not in filters:
            return _invalid("portfolio requires FUND as a product_type or asset.")
        equity_types = [EquityType(value.upper()) for value in raw_equity_types]
        if equity_types and ProductType.STOCK_ETF not in filters:
            return _invalid(
                "equity_type requires STOCK_ETF as a product_type or asset."
            )
        wallet_ids = sorted({UUID(value) for value in raw_wallet_ids}, key=str)
        if wallet_ids and ProductType.CRYPTO not in filters:
            return _invalid("wallet_id requires CRYPTO as a product_type or asset.")
        assets = [
            GainsAssetFilter(
                product_type=product_type,
                asset_keys=sorted(asset_keys) if asset_keys is not None else [],
                portfolio_names=(
                    portfolio_names if product_type == ProductType.FUND else []
                ),
                equity_types=(
                    equity_types if product_type == ProductType.STOCK_ETF else []
                ),
                wallet_ids=(wallet_ids if product_type == ProductType.CRYPTO else []),
            )
            for product_type, asset_keys in filters.items()
        ]
    except ValueError as error:
        return _invalid(str(error))

    entities = []
    for raw_entity in request.args.getlist("entity"):
        try:
            entities.append(UUID(raw_entity))
        except ValueError:
            return _invalid(f"Invalid entity UUID: {raw_entity}")

    from_date_param = request.args.get("from_date")
    to_date_param = request.args.get("to_date")
    try:
        from_date = date.fromisoformat(from_date_param) if from_date_param else None
        to_date = date.fromisoformat(to_date_param) if to_date_param else None
    except ValueError:
        return _invalid("Invalid date format. Use YYYY-MM-DD.")
    if from_date and to_date and from_date > to_date:
        return _invalid("from_date must be before or equal to to_date")

    try:
        accrue_fixed_income = FixedIncomeAccrual(
            request.args.get(
                "accrue_fixed_income", FixedIncomeAccrual.NONE.value
            ).upper()
        )
    except ValueError:
        return _invalid("Invalid accrue_fixed_income. Use NONE, NET, or GROSS.")
    try:
        calculation_mode = GainsCalculationMode(
            request.args.get(
                "calculation_mode", GainsCalculationMode.HYBRID.value
            ).upper()
        )
    except ValueError:
        return _invalid("Invalid calculation_mode. Use HYBRID or SNAPSHOTS.")
    result = await get_gains_timeline_uc.execute(
        GainsTimelineQuery(
            assets=assets,
            base_currency=base_currency,
            entities=entities or None,
            from_date=from_date,
            to_date=to_date,
            accrue_fixed_income=accrue_fixed_income,
            calculation_mode=calculation_mode,
        )
    )
    return jsonify(
        {
            "currency": result.currency,
            "method": result.method.value,
            "basis": result.basis.value,
            "quality": result.quality.value,
            "basis_status": result.basis_status.value,
            "xirr": result.xirr,
            "annualized_xirr": result.annualized_xirr,
            "opening_value": result.opening_value,
            "warnings": [warning.value for warning in result.warnings],
            "not_applicable_reasons": [
                reason.value for reason in result.not_applicable_reasons
            ],
            "points": [
                {
                    "date": point.date.isoformat(),
                    **_serialize_metrics(point.metrics),
                    "breakdown": {
                        product_type: _serialize_metrics(metrics)
                        for product_type, metrics in point.breakdown.items()
                    },
                    "estimated": point.estimated,
                }
                for point in result.points
            ],
        }
    ), 200
