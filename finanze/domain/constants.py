from domain.dezimal import Dezimal

CAPITAL_GAINS_BASE_TAX = Dezimal(0.19)

SUPPORTED_CURRENCIES = ["EUR", "USD"]

# Pegged 1:1 to another currency; no independent market rate is fetched.
CURRENCY_ALIASES = {
    "BNFCR": "USD",
    "PUSD": "USD",
}


def resolve_currency_alias(currency: str | None) -> str | None:
    if not currency:
        return currency
    return CURRENCY_ALIASES.get(currency.upper(), currency)
