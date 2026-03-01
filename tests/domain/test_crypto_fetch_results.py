from uuid import uuid4

from domain.crypto import (
    CryptoCurrencyType,
    CryptoFetchedPosition,
    CryptoFetchResult,
    CryptoFetchResults,
)
from domain.dezimal import Dezimal


def _native(symbol: str, balance: str) -> CryptoFetchedPosition:
    return CryptoFetchedPosition(
        id=uuid4(),
        symbol=symbol,
        balance=Dezimal(balance),
        type=CryptoCurrencyType.NATIVE,
    )


def _token(
    symbol: str, balance: str, contract: str, name: str | None = None
) -> CryptoFetchedPosition:
    return CryptoFetchedPosition(
        id=uuid4(),
        symbol=symbol,
        balance=Dezimal(balance),
        type=CryptoCurrencyType.TOKEN,
        contract_address=contract,
        name=name,
    )


def _result(
    address: str, assets: list[CryptoFetchedPosition], has_txs: bool | None = None
) -> CryptoFetchResult:
    return CryptoFetchResult(address=address, assets=assets, has_txs=has_txs)


class TestAssetKey:
    def test_native_uses_type_and_symbol(self):
        asset = _native("BTC", "1")
        key = CryptoFetchResults._asset_key(asset)
        assert key == (CryptoCurrencyType.NATIVE, "BTC")

    def test_token_uses_type_and_contract(self):
        asset = _token("USDT", "100", "0xdac17f958d2ee523a2206206994597c13d831ec7")
        key = CryptoFetchResults._asset_key(asset)
        assert key == (
            CryptoCurrencyType.TOKEN,
            "0xdac17f958d2ee523a2206206994597c13d831ec7",
        )

    def test_token_without_contract_falls_back_to_symbol(self):
        asset = CryptoFetchedPosition(
            id=uuid4(),
            symbol="USDT",
            balance=Dezimal("100"),
            type=CryptoCurrencyType.TOKEN,
            contract_address=None,
        )
        key = CryptoFetchResults._asset_key(asset)
        assert key == (CryptoCurrencyType.TOKEN, "USDT")

    def test_same_symbol_different_contracts_produce_different_keys(self):
        a = _token("USDT", "50", "0xaaa")
        b = _token("USDT", "50", "0xbbb")
        assert CryptoFetchResults._asset_key(a) != CryptoFetchResults._asset_key(b)

    def test_same_symbol_native_vs_token_produce_different_keys(self):
        native = _native("ETH", "1")
        token = _token("ETH", "1", "0xaaa")
        assert CryptoFetchResults._asset_key(native) != CryptoFetchResults._asset_key(
            token
        )


class TestMergeResults:
    def test_merges_native_balances_by_symbol(self):
        existing = _result("addr1", [_native("BTC", "1")])
        incoming = _result("addr1", [_native("BTC", "2")])

        CryptoFetchResults._merge_results(existing, incoming)

        assert len(existing.assets) == 1
        assert existing.assets[0].balance == Dezimal("3")

    def test_adds_new_asset_when_key_differs(self):
        existing = _result("addr1", [_native("BTC", "1")])
        incoming = _result("addr1", [_native("ETH", "5")])

        CryptoFetchResults._merge_results(existing, incoming)

        assert len(existing.assets) == 2
        symbols = {a.symbol for a in existing.assets}
        assert symbols == {"BTC", "ETH"}

    def test_tokens_with_same_symbol_different_contracts_not_merged(self):
        existing = _result("addr1", [_token("USDT", "100", "0xaaa")])
        incoming = _result("addr1", [_token("USDT", "200", "0xbbb")])

        CryptoFetchResults._merge_results(existing, incoming)

        assert len(existing.assets) == 2
        balances = sorted([a.balance for a in existing.assets], key=lambda d: d.val)
        assert balances[0] == Dezimal("100")
        assert balances[1] == Dezimal("200")

    def test_tokens_with_same_contract_are_merged(self):
        existing = _result("addr1", [_token("USDT", "100", "0xaaa")])
        incoming = _result("addr1", [_token("USDT", "50", "0xaaa")])

        CryptoFetchResults._merge_results(existing, incoming)

        assert len(existing.assets) == 1
        assert existing.assets[0].balance == Dezimal("150")

    def test_has_txs_propagated_when_incoming_is_true(self):
        existing = _result("addr1", [], has_txs=False)
        incoming = _result("addr1", [], has_txs=True)

        CryptoFetchResults._merge_results(existing, incoming)

        assert existing.has_txs is True

    def test_has_txs_not_overwritten_when_incoming_is_none(self):
        existing = _result("addr1", [], has_txs=True)
        incoming = _result("addr1", [], has_txs=None)

        CryptoFetchResults._merge_results(existing, incoming)

        assert existing.has_txs is True


class TestAdd:
    def test_add_disjoint_addresses(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "1")])}
        )
        b = CryptoFetchResults(
            results={"addr2": _result("addr2", [_native("ETH", "2")])}
        )

        combined = a + b

        assert "addr1" in combined.results
        assert "addr2" in combined.results
        assert len(combined.results) == 2

    def test_add_overlapping_address_merges_assets(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "1")])}
        )
        b = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "3")])}
        )

        combined = a + b

        assert len(combined.results) == 1
        assert len(combined.results["addr1"].assets) == 1
        assert combined.results["addr1"].assets[0].balance == Dezimal("4")

    def test_add_none_result_replaced_by_non_none(self):
        a = CryptoFetchResults(results={"addr1": None})
        b = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "1")])}
        )

        combined = a + b

        assert combined.results["addr1"] is not None
        assert combined.results["addr1"].assets[0].balance == Dezimal("1")

    def test_add_non_none_not_replaced_by_none(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "5")])}
        )
        b = CryptoFetchResults(results={"addr1": None})

        combined = a + b

        assert combined.results["addr1"] is not None
        assert combined.results["addr1"].assets[0].balance == Dezimal("5")

    def test_add_empty_results(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "1")])}
        )
        b = CryptoFetchResults(results={})

        combined = a + b

        assert combined.results == a.results

    def test_add_does_not_mutate_originals(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_native("BTC", "1")])}
        )
        b = CryptoFetchResults(
            results={"addr2": _result("addr2", [_native("ETH", "2")])}
        )

        _ = a + b

        assert "addr2" not in a.results
        assert "addr1" not in b.results

    def test_add_preserves_tokens_with_same_symbol_different_contracts(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_token("USDT", "100", "0xaaa")])}
        )
        b = CryptoFetchResults(
            results={"addr1": _result("addr1", [_token("USDT", "200", "0xbbb")])}
        )

        combined = a + b

        assert len(combined.results["addr1"].assets) == 2

    def test_add_merges_tokens_with_same_contract(self):
        a = CryptoFetchResults(
            results={"addr1": _result("addr1", [_token("USDT", "100", "0xaaa")])}
        )
        b = CryptoFetchResults(
            results={"addr1": _result("addr1", [_token("USDT", "50", "0xaaa")])}
        )

        combined = a + b

        assert len(combined.results["addr1"].assets) == 1
        assert combined.results["addr1"].assets[0].balance == Dezimal("150")

    def test_add_mixed_native_and_tokens(self):
        a = CryptoFetchResults(
            results={
                "addr1": _result(
                    "addr1",
                    [
                        _native("ETH", "2"),
                        _token("USDT", "100", "0xdac"),
                    ],
                )
            }
        )
        b = CryptoFetchResults(
            results={
                "addr1": _result(
                    "addr1",
                    [
                        _native("ETH", "3"),
                        _token("USDT", "50", "0xdac"),
                        _token("LINK", "10", "0x514"),
                    ],
                )
            }
        )

        combined = a + b

        assets = combined.results["addr1"].assets
        assert len(assets) == 3
        by_key = {CryptoFetchResults._asset_key(a): a for a in assets}
        assert by_key[(CryptoCurrencyType.NATIVE, "ETH")].balance == Dezimal("5")
        assert by_key[(CryptoCurrencyType.TOKEN, "0xdac")].balance == Dezimal("150")
        assert by_key[(CryptoCurrencyType.TOKEN, "0x514")].balance == Dezimal("10")
