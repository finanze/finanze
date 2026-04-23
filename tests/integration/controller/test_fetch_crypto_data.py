import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import (
    AddressSource,
    CryptoFetchResult,
    CryptoFetchResults,
    CryptoFetchedPosition,
    CryptoCurrencyType,
    CryptoWallet,
    HDAddress,
    HDWallet,
)
from domain.dezimal import Dezimal
from domain.native_entities import BITCOIN, ETHEREUM
from domain.public_key import (
    CoinType,
    DerivedAddress,
    DerivedAddressesResult,
    ScriptType,
)

FETCH_CRYPTO_URL = "/api/v1/data/fetch/crypto"
GET_POSITIONS_URL = "/api/v1/positions"

BITCOIN_ID = "c0000000-0000-0000-0000-000000000001"
ETHEREUM_ID = "c0000000-0000-0000-0000-000000000002"


def _setup_crypto_fetcher(crypto_entity_fetchers, entity, fetch_results):
    fetcher = MagicMock(spec=CryptoEntityFetcher)
    fetcher.fetch = AsyncMock(return_value=fetch_results)
    crypto_entity_fetchers[entity] = fetcher
    return fetcher


def _make_fetch_result(address, symbol="ETH", balance="1.5"):
    return CryptoFetchResult(
        address=address,
        assets=[
            CryptoFetchedPosition(
                id=None,
                symbol=symbol,
                balance=Dezimal(balance),
                type=CryptoCurrencyType.NATIVE,
            )
        ],
        has_txs=True,
    )


class TestFetchCryptoValidation:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_entity(self, client, crypto_wallet_port):
        crypto_wallet_port.get_connected_entities = AsyncMock(return_value=set())
        response = await client.post(
            FETCH_CRYPTO_URL,
            json={"entity": str(uuid.uuid4())},
        )
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_not_connected_when_no_wallets(
        self, client, crypto_wallet_port
    ):
        crypto_wallet_port.get_connected_entities = AsyncMock(return_value=set())
        response = await client.post(
            FETCH_CRYPTO_URL,
            json={"entity": ETHEREUM_ID},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "NOT_CONNECTED"


class TestFetchCryptoManualWallet:
    @pytest.mark.asyncio
    async def test_fetch_manual_wallet_completed(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
        last_fetches_port,
        position_port,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
    ):
        wallet_id = uuid.uuid4()
        address = "0xabc123def456"

        crypto_wallet_port.get_connected_entities = AsyncMock(
            return_value={uuid.UUID(ETHEREUM_ID)}
        )
        crypto_wallet_port.get_by_entity_id = AsyncMock(
            return_value=[
                CryptoWallet(
                    id=wallet_id,
                    entity_id=uuid.UUID(ETHEREUM_ID),
                    addresses=[address],
                    name="My ETH Wallet",
                    address_source=AddressSource.MANUAL,
                    hd_wallet=None,
                )
            ]
        )
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])

        fetch_results = CryptoFetchResults(
            results={address: _make_fetch_result(address)}
        )
        _setup_crypto_fetcher(crypto_entity_fetchers, ETHEREUM, fetch_results)

        crypto_asset_registry_port.get_by_symbol = AsyncMock(return_value=None)
        crypto_asset_info_provider.get_by_symbol = AsyncMock(return_value=[])
        crypto_asset_info_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"ETH": {"EUR": Dezimal("2000")}}
        )
        crypto_asset_info_provider.get_prices_by_addresses = AsyncMock(return_value={})

        response = await client.post(
            FETCH_CRYPTO_URL,
            json={"entity": ETHEREUM_ID},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        position_port.save.assert_awaited_once()
        last_fetches_port.save.assert_awaited_once()

        # Read-after-write: verify crypto position via GET /positions
        saved_position = position_port.save.await_args[0][0]
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={ETHEREUM: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()

        assert ETHEREUM_ID in pos_body["positions"]
        crypto_entries = pos_body["positions"][ETHEREUM_ID][0]["products"]["CRYPTO"][
            "entries"
        ]
        assert len(crypto_entries) == 1
        eth_assets = crypto_entries[0]["assets"]
        eth = next(a for a in eth_assets if a["symbol"] == "ETH")
        assert eth["amount"] == 1.5

    @pytest.mark.asyncio
    async def test_fetch_manual_wallet_multiple_addresses(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
        last_fetches_port,
        position_port,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
    ):
        wallet_id = uuid.uuid4()
        addr1 = "0xaddr1"
        addr2 = "0xaddr2"

        crypto_wallet_port.get_connected_entities = AsyncMock(
            return_value={uuid.UUID(ETHEREUM_ID)}
        )
        crypto_wallet_port.get_by_entity_id = AsyncMock(
            return_value=[
                CryptoWallet(
                    id=wallet_id,
                    entity_id=uuid.UUID(ETHEREUM_ID),
                    addresses=[addr1, addr2],
                    name="Multi Addr Wallet",
                    address_source=AddressSource.MANUAL,
                    hd_wallet=None,
                )
            ]
        )
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])

        fetch_results = CryptoFetchResults(
            results={
                addr1: _make_fetch_result(addr1, "ETH", "1.0"),
                addr2: _make_fetch_result(addr2, "ETH", "2.5"),
            }
        )
        _setup_crypto_fetcher(crypto_entity_fetchers, ETHEREUM, fetch_results)

        crypto_asset_registry_port.get_by_symbol = AsyncMock(return_value=None)
        crypto_asset_info_provider.get_by_symbol = AsyncMock(return_value=[])
        crypto_asset_info_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"ETH": {"EUR": Dezimal("2000")}}
        )
        crypto_asset_info_provider.get_prices_by_addresses = AsyncMock(return_value={})

        response = await client.post(
            FETCH_CRYPTO_URL,
            json={"entity": ETHEREUM_ID},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"

        saved_position = position_port.save.await_args[0][0]
        from domain.global_position import ProductType

        crypto_products = saved_position.products[ProductType.CRYPTO]
        wallet_data = crypto_products.entries[0]
        eth_asset = next(a for a in wallet_data.assets if a.symbol == "ETH")
        assert eth_asset.amount == Dezimal("3.5")

        # Read-after-write: verify aggregated position via GET /positions
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={ETHEREUM: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()

        crypto_entries = pos_body["positions"][ETHEREUM_ID][0]["products"]["CRYPTO"][
            "entries"
        ]
        assert len(crypto_entries) == 1
        eth_assets = crypto_entries[0]["assets"]
        eth = next(a for a in eth_assets if a["symbol"] == "ETH")
        assert eth["amount"] == 3.5


class TestFetchCryptoXpubWallet:
    @pytest.mark.asyncio
    async def test_fetch_xpub_wallet_with_known_addresses(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
        last_fetches_port,
        position_port,
        public_key_derivation,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
    ):
        wallet_id = uuid.uuid4()
        hd_addr = HDAddress(
            address="bc1qknown",
            index=0,
            change=0,
            path="m/84'/0'/0'/0/0",
            pubkey="pub0",
        )
        xpub_wallet = CryptoWallet(
            id=wallet_id,
            entity_id=uuid.UUID(BITCOIN_ID),
            addresses=[],
            name="My BTC HD",
            address_source=AddressSource.DERIVED,
            hd_wallet=HDWallet(
                xpub="xpub6CatV...",
                addresses=[hd_addr],
                script_type=ScriptType.P2WPKH,
                coin_type=CoinType.BITCOIN,
            ),
        )

        crypto_wallet_port.get_connected_entities = AsyncMock(
            return_value={uuid.UUID(BITCOIN_ID)}
        )
        crypto_wallet_port.get_by_entity_id = AsyncMock(return_value=[xpub_wallet])
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])

        _setup_crypto_fetcher(
            crypto_entity_fetchers,
            BITCOIN,
            CryptoFetchResults(
                results={
                    "bc1qknown": CryptoFetchResult(
                        address="bc1qknown",
                        assets=[
                            CryptoFetchedPosition(
                                id=None,
                                symbol="BTC",
                                balance=Dezimal("0.5"),
                                type=CryptoCurrencyType.NATIVE,
                            )
                        ],
                        has_txs=True,
                    )
                }
            ),
        )

        # Discovery derivation returns empty batches to stop gap scanning
        public_key_derivation.calculate = MagicMock(
            return_value=DerivedAddressesResult(
                key_type="xpub",
                script_type=ScriptType.P2WPKH,
                coin=CoinType.BITCOIN,
                receiving=[],
                change=[],
            )
        )

        crypto_asset_registry_port.get_by_symbol = AsyncMock(return_value=None)
        crypto_asset_info_provider.get_by_symbol = AsyncMock(return_value=[])
        crypto_asset_info_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"BTC": {"EUR": Dezimal("50000")}}
        )
        crypto_asset_info_provider.get_prices_by_addresses = AsyncMock(return_value={})

        response = await client.post(
            FETCH_CRYPTO_URL,
            json={"entity": BITCOIN_ID},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        position_port.save.assert_awaited_once()

        saved_position = position_port.save.await_args[0][0]
        from domain.global_position import ProductType

        crypto_products = saved_position.products[ProductType.CRYPTO]
        wallet_data = crypto_products.entries[0]
        btc_asset = next(a for a in wallet_data.assets if a.symbol == "BTC")
        assert btc_asset.amount == Dezimal("0.5")

        # Read-after-write: verify BTC position via GET /positions
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={BITCOIN: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()

        crypto_entries = pos_body["positions"][BITCOIN_ID][0]["products"]["CRYPTO"][
            "entries"
        ]
        btc_assets = crypto_entries[0]["assets"]
        btc = next(a for a in btc_assets if a["symbol"] == "BTC")
        assert btc["amount"] == 0.5

    @pytest.mark.asyncio
    async def test_fetch_xpub_discovers_new_addresses(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
        last_fetches_port,
        position_port,
        public_key_derivation,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
    ):
        wallet_id = uuid.uuid4()
        xpub_wallet = CryptoWallet(
            id=wallet_id,
            entity_id=uuid.UUID(BITCOIN_ID),
            addresses=[],
            name="Discovery BTC HD",
            address_source=AddressSource.DERIVED,
            hd_wallet=HDWallet(
                xpub="xpub6Disc...",
                addresses=[],
                script_type=ScriptType.P2WPKH,
                coin_type=CoinType.BITCOIN,
            ),
        )

        crypto_wallet_port.get_connected_entities = AsyncMock(
            return_value={uuid.UUID(BITCOIN_ID)}
        )
        crypto_wallet_port.get_by_entity_id = AsyncMock(return_value=[xpub_wallet])
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])

        derived_addr = DerivedAddress(
            index=0,
            path="m/84'/0'/0'/0/0",
            address="bc1qnew0",
            pubkey="pubnew0",
            change=0,
        )

        call_count = 0

        def derivation_side_effect(req):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return DerivedAddressesResult(
                    key_type="xpub",
                    script_type=ScriptType.P2WPKH,
                    coin=CoinType.BITCOIN,
                    receiving=[derived_addr],
                    change=[],
                )
            return DerivedAddressesResult(
                key_type="xpub",
                script_type=ScriptType.P2WPKH,
                coin=CoinType.BITCOIN,
                receiving=[],
                change=[],
            )

        public_key_derivation.calculate = MagicMock(side_effect=derivation_side_effect)

        def fetch_side_effect(request):
            results = {}
            for addr in request.addresses:
                if addr == "bc1qnew0":
                    results[addr] = CryptoFetchResult(
                        address=addr,
                        assets=[
                            CryptoFetchedPosition(
                                id=None,
                                symbol="BTC",
                                balance=Dezimal("0.25"),
                                type=CryptoCurrencyType.NATIVE,
                            )
                        ],
                        has_txs=True,
                    )
                else:
                    results[addr] = CryptoFetchResult(
                        address=addr, assets=[], has_txs=False
                    )
            return CryptoFetchResults(results=results)

        fetcher = MagicMock(spec=CryptoEntityFetcher)
        fetcher.fetch = AsyncMock(side_effect=fetch_side_effect)
        crypto_entity_fetchers[BITCOIN] = fetcher

        crypto_asset_registry_port.get_by_symbol = AsyncMock(return_value=None)
        crypto_asset_info_provider.get_by_symbol = AsyncMock(return_value=[])
        crypto_asset_info_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"BTC": {"EUR": Dezimal("50000")}}
        )
        crypto_asset_info_provider.get_prices_by_addresses = AsyncMock(return_value={})

        response = await client.post(
            FETCH_CRYPTO_URL,
            json={"entity": BITCOIN_ID},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"

        crypto_wallet_port.insert_hd_addresses.assert_awaited_once()
        saved_wallet_id = crypto_wallet_port.insert_hd_addresses.await_args[0][0]
        saved_hd_addrs = crypto_wallet_port.insert_hd_addresses.await_args[0][1]
        assert saved_wallet_id == wallet_id
        assert len(saved_hd_addrs) == 1
        assert saved_hd_addrs[0].address == "bc1qnew0"

        # Read-after-write: verify discovered address position via GET /positions
        position_port.save.assert_awaited_once()
        saved_position = position_port.save.await_args[0][0]
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={BITCOIN: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()

        crypto_entries = pos_body["positions"][BITCOIN_ID][0]["products"]["CRYPTO"][
            "entries"
        ]
        btc_assets = crypto_entries[0]["assets"]
        btc = next(a for a in btc_assets if a["symbol"] == "BTC")
        assert btc["amount"] == 0.25


class TestFetchCryptoAllEntities:
    @pytest.mark.asyncio
    async def test_fetches_all_connected_entities_when_no_entity_specified(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
        last_fetches_port,
        position_port,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
    ):
        eth_wallet_id = uuid.uuid4()
        crypto_wallet_port.get_connected_entities = AsyncMock(
            return_value={uuid.UUID(ETHEREUM_ID)}
        )
        crypto_wallet_port.get_by_entity_id = AsyncMock(
            return_value=[
                CryptoWallet(
                    id=eth_wallet_id,
                    entity_id=uuid.UUID(ETHEREUM_ID),
                    addresses=["0xall"],
                    name="All Wallet",
                    address_source=AddressSource.MANUAL,
                    hd_wallet=None,
                )
            ]
        )
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])

        _setup_crypto_fetcher(
            crypto_entity_fetchers,
            ETHEREUM,
            CryptoFetchResults(results={"0xall": _make_fetch_result("0xall")}),
        )

        crypto_asset_registry_port.get_by_symbol = AsyncMock(return_value=None)
        crypto_asset_info_provider.get_by_symbol = AsyncMock(return_value=[])
        crypto_asset_info_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"ETH": {"EUR": Dezimal("2000")}}
        )
        crypto_asset_info_provider.get_prices_by_addresses = AsyncMock(return_value={})

        response = await client.post(
            FETCH_CRYPTO_URL,
            json={},
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["code"] == "COMPLETED"
        position_port.save.assert_awaited_once()

        # Read-after-write: verify position via GET /positions
        saved_position = position_port.save.await_args[0][0]
        position_port.get_last_by_entity_broken_down = AsyncMock(
            return_value={ETHEREUM: [saved_position]}
        )
        get_resp = await client.get(GET_POSITIONS_URL)
        assert get_resp.status_code == 200
        pos_body = await get_resp.get_json()

        assert ETHEREUM_ID in pos_body["positions"]
        crypto_entries = pos_body["positions"][ETHEREUM_ID][0]["products"]["CRYPTO"][
            "entries"
        ]
        assert len(crypto_entries) == 1
        eth_assets = crypto_entries[0]["assets"]
        eth = next(a for a in eth_assets if a["symbol"] == "ETH")
        assert eth["amount"] == 1.5
