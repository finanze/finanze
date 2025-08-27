from datetime import date

from flask import jsonify, request

from domain.dezimal import Dezimal
from domain.forecast import ForecastRequest
from domain.use_cases.forecast import Forecast


def forecast(forecast_uc: Forecast):
    body = request.json or {}

    try:
        target_date_raw = body["target_date"]
        target_date = (
            date.fromisoformat(target_date_raw)
            if isinstance(target_date_raw, str)
            else target_date_raw
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    avg_increase_val = body.get("avg_annual_market_increase")
    avg_increase: Dezimal | None = None
    if avg_increase_val is not None:
        try:
            avg_increase = Dezimal(avg_increase_val)
        except Exception as e:
            return jsonify(
                {
                    "code": "INVALID_REQUEST",
                    "message": f"avg_annual_market_increase: {e}",
                }
            ), 400

    try:
        result = forecast_uc.execute(
            ForecastRequest(
                target_date=target_date, avg_annual_market_increase=avg_increase
            )
        )
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return jsonify(result), 200
