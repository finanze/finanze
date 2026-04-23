from dataclasses import asdict

from domain.use_cases.get_euribor_rates import GetEuriborRates
from quart import jsonify


async def get_euribor_rates(get_euribor_rates_uc: GetEuriborRates):
    result = await get_euribor_rates_uc.execute()
    return jsonify(asdict(result)), 200
