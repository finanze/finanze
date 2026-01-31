from domain.use_cases.get_exchange_rates import GetExchangeRates
from quart import jsonify, request


async def exchange_rates(get_exchange_rates_uc: GetExchangeRates):
    cached = request.args.get("cached", "false").lower() in ("true", "1", "yes")

    rates = await get_exchange_rates_uc.execute(cached=cached)
    return jsonify(rates), 200
