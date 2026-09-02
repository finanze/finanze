from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.crypto import CryptoCurrencyType, CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient
from infrastructure.client.crypto.ethplorer.ethplorer_client import EthplorerClient
from infrastructure.client.entity.crypto.ethereum.ethereum_fetcher import (
    EthereumFetcher,
)

FAKE_ADDRESS = "0xfake00000000000000000000000000000000a001"
TOKEN_CONTRACT = "0xAAAA000000000000000000000000000000A001"
ETHPLORER_INTEGRATIONS = {
    ExternalIntegrationId.ETHPLORER: {"api_key": "fake-ethplorer-key"}
}
ETHERSCAN_INTEGRATIONS = {
    ExternalIntegrationId.ETHERSCAN: {"api_key": "fake-etherscan-key"}
}


def _ethplorer_payload():
    return {
        "ETH": {"rawBalance": "1500000000000000000"},
        "tokens": [
            {
                "tokenInfo": {
                    "address": TOKEN_CONTRACT,
                    "name": "Fake Tether",
                    "symbol": "USDT",
                    "decimals": "6",
                },
                "balance": 2500000,
            }
        ],
    }


async def _etherscan_fetch(**kwargs):
    action = kwargs["action"]
    if action == "balance":
        return "1500000000000000000"
    if action == "tokentx":
        return [
            {
                "contractAddress": TOKEN_CONTRACT,
                "tokenSymbol": "USDT",
                "tokenName": "Fake Tether",
                "tokenDecimal": "6",
            }
        ]
    if action == "tokenbalance":
        return "2500000"
    raise AssertionError(f"unexpected etherscan action {action}")


def _build():
    etherscan_client = MagicMock(spec=EtherscanClient)
    etherscan_client.fetch = AsyncMock(side_effect=_etherscan_fetch)
    ethplorer_client = MagicMock(spec=EthplorerClient)
    ethplorer_client.fetch_address_info = AsyncMock(return_value=_ethplorer_payload())
    return EthereumFetcher(etherscan_client, ethplorer_client), ethplorer_client


def _assert_ethereum_positions(result):
    assert result is not None
    by_type = {a.type: a for a in result.assets}
    native = by_type[CryptoCurrencyType.NATIVE]
    token = by_type[CryptoCurrencyType.TOKEN]

    assert native.symbol == "ETH"
    assert native.balance == Dezimal("1.5")
    assert native.chain == "ethereum"

    assert token.symbol == "USDT"
    assert token.contract_address == TOKEN_CONTRACT.lower()
    assert token.balance == Dezimal("2.5")
    assert token.chain == "ethereum"


class TestEthereumFetcherChain:
    @pytest.mark.asyncio
    async def test_ethplorer_positions_carry_chain(self):
        fetcher, _ = _build()

        results = await fetcher.fetch(
            CryptoFetchRequest(
                integrations=ETHPLORER_INTEGRATIONS, addresses=[FAKE_ADDRESS]
            )
        )

        _assert_ethereum_positions(results.results[FAKE_ADDRESS])

    @pytest.mark.asyncio
    async def test_etherscan_positions_carry_chain(self):
        fetcher, ethplorer_client = _build()

        results = await fetcher.fetch(
            CryptoFetchRequest(
                integrations=ETHERSCAN_INTEGRATIONS, addresses=[FAKE_ADDRESS]
            )
        )

        _assert_ethereum_positions(results.results[FAKE_ADDRESS])
        ethplorer_client.fetch_address_info.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_address_stays_none(self):
        fetcher, ethplorer_client = _build()
        ethplorer_client.fetch_address_info = AsyncMock(side_effect=AddressNotFound())

        results = await fetcher.fetch(
            CryptoFetchRequest(
                integrations=ETHPLORER_INTEGRATIONS, addresses=[FAKE_ADDRESS]
            )
        )

        assert results.results == {FAKE_ADDRESS: None}
