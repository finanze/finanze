READ_ONLY_NOTE = "Modifications are disabled, data can only be read. The user can allow them in the Finanze settings."

INSTRUCTIONS = """Finanze is the user's self-hosted personal finance app. It aggregates banks, brokers, crypto wallets, commodities, real estate and manual data.

- Call get_context first to know today's date, timezone and default currency.
- Use list_entities to resolve entity and account IDs before filtering by them.
- Amounts are in the stated currency, rates and returns are fractions (0.05 = 5%).
- Prefer get_net_worth for an overview and narrow down with get_positions, search_transactions or get_cashflow.
- Always confirm with the user before modifying or deleting data.
"""


def build_instructions(read_only: bool) -> str:
    if read_only:
        return f"{INSTRUCTIONS}- {READ_ONLY_NOTE}\n"
    return INSTRUCTIONS
