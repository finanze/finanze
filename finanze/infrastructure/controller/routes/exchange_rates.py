from domain.use_cases.get_exchange_rates import GetExchangeRates
from flask import jsonify


def exchange_rates(get_exchange_rates_uc: GetExchangeRates):
    rates = get_exchange_rates_uc.execute()
    return jsonify(rates), 200
