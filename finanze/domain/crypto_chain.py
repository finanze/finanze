from typing import Final


CHAIN_ALIASES: Final = {
    "ethereum": "1",
    "optimism": "10",
    "bsc": "56",
    "binance-smart-chain": "56",
    "gnosis": "100",
    "polygon": "137",
    "fantom": "250",
    "zksync": "324",
    "zksync-era": "324",
    "base": "8453",
    "arbitrum": "42161",
    "avalanche": "43114",
    "celo": "42220",
    "linea": "59144",
    "scroll": "534352",
    "blast": "81457",
}


def normalize_crypto_chain(chain: str | None) -> str | None:
    if chain is None:
        return None
    normalized = chain.strip().lower()
    return CHAIN_ALIASES.get(normalized, normalized) or None
