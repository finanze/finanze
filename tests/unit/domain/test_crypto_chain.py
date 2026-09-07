import pytest

from domain.crypto_chain import normalize_crypto_chain


@pytest.mark.parametrize(
    ("chain", "expected"),
    [
        ("ethereum", "1"),
        ("optimism", "10"),
        ("bsc", "56"),
        ("binance-smart-chain", "56"),
        ("gnosis", "100"),
        ("polygon", "137"),
        ("fantom", "250"),
        ("zksync", "324"),
        ("zksync-era", "324"),
        ("base", "8453"),
        ("arbitrum", "42161"),
        ("avalanche", "43114"),
        ("celo", "42220"),
        ("linea", "59144"),
        ("scroll", "534352"),
        ("blast", "81457"),
        ("bitcoin", "bitcoin"),
        ("litecoin", "litecoin"),
        ("tron", "tron"),
        ("solana", "solana"),
        ("1", "1"),
        (" ETHEREUM ", "1"),
        (" Future-Chain ", "future-chain"),
        (None, None),
        ("", None),
        ("  ", None),
    ],
)
def test_normalizes_chain_identifiers(chain: str | None, expected: str | None) -> None:
    assert normalize_crypto_chain(chain) == expected
