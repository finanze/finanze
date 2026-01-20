from domain.use_cases.get_exchange_rates import GetExchangeRates
from quart import jsonify


async def exchange_rates(get_exchange_rates_uc: GetExchangeRates):
    rates = await get_exchange_rates_uc.execute()
    return jsonify(rates), 200
