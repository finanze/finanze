from datetime import date

from domain.dezimal import Dezimal
from domain.forecast import ForecastRequest
from domain.use_cases.forecast import Forecast
from flask import jsonify, request


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
    avg_crypto_increase_val = body.get("avg_annual_crypto_increase")
    avg_crypto_increase = Dezimal(0)
    avg_commodity_increase_val = body.get("avg_annual_commodity_increase")
    avg_commodity_increase = Dezimal(0)
    try:
        avg_increase = (
            Dezimal(avg_increase_val) if avg_increase_val is not None else None
        )
        avg_crypto_increase = (
            Dezimal(avg_crypto_increase_val)
            if avg_crypto_increase_val is not None
            else Dezimal(0)
        )
        avg_commodity_increase = (
            Dezimal(avg_commodity_increase_val)
            if avg_commodity_increase_val is not None
            else Dezimal(0)
        )
    except Exception as e:
        return jsonify(
            {
                "code": "INVALID_REQUEST",
                "message": f"Some number formats are wrong: {e}",
            }
        ), 400

    try:
        result = forecast_uc.execute(
            ForecastRequest(
                target_date=target_date,
                avg_annual_market_increase=avg_increase,
                avg_annual_crypto_increase=avg_crypto_increase,
                avg_annual_commodity_increase=avg_commodity_increase,
            )
        )
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return jsonify(result), 200
