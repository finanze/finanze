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
    HDWallet,
    HDAddress,
)
from domain.dezimal import Dezimal
from domain.native_entities import ETHEREUM, NATIVE_ENTITIES
from domain.entity import EntityType
from domain.public_key import CoinType, DerivedAddressesResult, ScriptType

CONNECT_URL = "/api/v1/crypto-wallet"
UPDATE_URL = "/api/v1/crypto-wallet"
GET_ENTITIES_URL = "/api/v1/entities"
GET_ADDRESSES_URL = "/api/v1/crypto-wallet/addresses"

BITCOIN_ID = "c0000000-0000-0000-0000-000000000001"
ETHEREUM_ID = "c0000000-0000-0000-0000-000000000002"


def _delete_url(wallet_id: str) -> str:
    return f"/api/v1/crypto-wallet/{wallet_id}"


def _setup_crypto_fetcher(crypto_entity_fetchers, entity, fetch_results):
    fetcher = MagicMock(spec=CryptoEntityFetcher)
    fetcher.fetch = AsyncMock(return_value=fetch_results)
    crypto_entity_fetchers[entity] = fetcher
    return fetcher


def _make_fetch_results(addresses):
    results = {}
    for addr in addresses:
        results[addr] = CryptoFetchResult(
            address=addr,
            assets=[
                CryptoFetchedPosition(
                    id=None,
                    symbol="ETH",
                    balance=Dezimal("1.5"),
                    type=CryptoCurrencyType.NATIVE,
                )
            ],
        )
    return CryptoFetchResults(results=results)


def _setup_get_entities_mocks(
    entity_port,
    credentials_port,
    last_fetches_port,
    virtual_import_registry,
    entity_account_port,
    crypto_wallet_port,
    wallets_by_entity,
):
    """Configure all mocks needed by GetAvailableEntitiesImpl.execute()."""
    crypto_entities = [e for e in NATIVE_ENTITIES if e.type == EntityType.CRYPTO_WALLET]
    entity_port.get_all = AsyncMock(return_value=crypto_entities)
    credentials_port.get_available_entities = AsyncMock(return_value=[])
    virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])
    entity_account_port.get_for_entities = AsyncMock(return_value={})

    async def get_wallets_for_entity(entity_id, hd_addresses=False):
        return wallets_by_entity.get(entity_id, [])

    crypto_wallet_port.get_by_entity_id = AsyncMock(side_effect=get_wallets_for_entity)
    last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])


class TestConnectValidation:
    @pytest.mark.asyncio
    async def test_returns_400_on_empty_body(self, client):
        response = await client.post(CONNECT_URL, json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_entity_id_missing(self, client):
        response = await client.post(
            CONNECT_URL,
            json={"addresses": ["0xabc"], "name": "My Wallet", "source": "MANUAL"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_name_missing(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": ["0xabc"],
                "source": "MANUAL",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_source_missing(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": ["0xabc"],
                "name": "My Wallet",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_source(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": ["0xabc"],
                "name": "My Wallet",
                "source": "INVALID",
            },
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "source" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_no_addresses_and_no_hd_params(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": [],
                "name": "My Wallet",
                "source": "MANUAL",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_xpub_without_script_type(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": BITCOIN_ID,
                "addresses": [],
                "name": "HD Wallet",
                "source": "DERIVED",
                "xpub": "xpub6ABC...",
            },
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "xpub" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_script_type_without_xpub(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": BITCOIN_ID,
                "addresses": [],
                "name": "HD Wallet",
                "source": "DERIVED",
                "script_type": "p2wpkh",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_script_type(self, client):
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": BITCOIN_ID,
                "addresses": [],
                "name": "HD Wallet",
                "source": "DERIVED",
                "xpub": "xpub6ABC...",
                "script_type": "INVALID",
            },
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "script_type" in body["message"].lower()


class TestConnectEntityNotFound:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_entity(self, client):
        random_id = str(uuid.uuid4())
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": random_id,
                "addresses": ["0xabc"],
                "name": "My Wallet",
                "source": "MANUAL",
            },
        )
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"


class TestConnectManualAndRead:
    @pytest.mark.asyncio
    async def test_connect_manual_then_visible_in_entities(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
        entity_port,
        credentials_port,
        last_fetches_port,
        virtual_import_registry,
        entity_account_port,
    ):
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        crypto_wallet_port.exists_by_entity_and_address = AsyncMock(return_value=False)
        _setup_crypto_fetcher(
            crypto_entity_fetchers,
            ETHEREUM,
            _make_fetch_results(["0xabc123"]),
        )
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": ["0xabc123"],
                "name": "My ETH Wallet",
                "source": "MANUAL",
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["failed"] == {}
        crypto_wallet_port.insert.assert_awaited_once()

        # Capture inserted wallet and verify via GET /entities
        inserted_wallet = crypto_wallet_port.insert.await_args[0][0]
        _setup_get_entities_mocks(
            entity_port,
            credentials_port,
            last_fetches_port,
            virtual_import_registry,
            entity_account_port,
            crypto_wallet_port,
            wallets_by_entity={uuid.UUID(ETHEREUM_ID): [inserted_wallet]},
        )
        get_resp = await client.get(GET_ENTITIES_URL)
        assert get_resp.status_code == 200
        entities_body = await get_resp.get_json()

        eth_entity = next(
            e for e in entities_body["entities"] if str(e["id"]) == ETHEREUM_ID
        )
        assert len(eth_entity["connected"]) == 1
        wallet = eth_entity["connected"][0]
        assert wallet["name"] == "My ETH Wallet"
        assert "0xabc123" in wallet["addresses"]
        assert wallet["address_source"] == "MANUAL"

    @pytest.mark.asyncio
    async def test_connect_manual_address_already_exists(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
    ):
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        crypto_wallet_port.exists_by_entity_and_address = AsyncMock(return_value=True)
        _setup_crypto_fetcher(
            crypto_entity_fetchers,
            ETHEREUM,
            _make_fetch_results(["0xabc123"]),
        )
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": ["0xabc123"],
                "name": "My ETH Wallet",
                "source": "MANUAL",
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert "0xabc123" in body["failed"]
        assert body["failed"]["0xabc123"] == "ADDRESS_ALREADY_EXISTS"
        crypto_wallet_port.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_connect_manual_address_not_found(
        self,
        client,
        crypto_entity_fetchers,
        crypto_wallet_port,
        external_integration_port,
    ):
        external_integration_port.get_payloads_by_type = AsyncMock(return_value={})
        crypto_wallet_port.exists_by_entity_and_address = AsyncMock(return_value=False)
        _setup_crypto_fetcher(
            crypto_entity_fetchers,
            ETHEREUM,
            CryptoFetchResults(results={"0xabc123": None}),
        )
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": ETHEREUM_ID,
                "addresses": ["0xabc123"],
                "name": "My ETH Wallet",
                "source": "MANUAL",
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert "0xabc123" in body["failed"]
        assert body["failed"]["0xabc123"] == "ADDRESS_NOT_FOUND"
        crypto_wallet_port.insert.assert_not_awaited()


class TestConnectDerivedAndRead:
    @pytest.mark.asyncio
    async def test_connect_derived_then_visible_in_entities(
        self,
        client,
        crypto_wallet_port,
        public_key_derivation,
        entity_port,
        credentials_port,
        last_fetches_port,
        virtual_import_registry,
        entity_account_port,
    ):
        crypto_wallet_port.exists_by_entity_and_xpub = AsyncMock(return_value=False)
        public_key_derivation.calculate = MagicMock(
            return_value=DerivedAddressesResult(
                key_type="xpub",
                script_type=ScriptType.P2WPKH,
                coin=CoinType.BITCOIN,
                receiving=[],
                change=[],
            )
        )
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": BITCOIN_ID,
                "addresses": [],
                "name": "My BTC HD Wallet",
                "source": "DERIVED",
                "xpub": "xpub6CatV...",
                "script_type": "p2wpkh",
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["failed"] == {}
        crypto_wallet_port.insert.assert_awaited_once()
        crypto_wallet_port.insert_hd_wallet.assert_awaited_once()

        # Build the wallet as it would appear after read
        inserted_wallet = crypto_wallet_port.insert.await_args[0][0]
        hd_wallet_args = crypto_wallet_port.insert_hd_wallet.await_args[0]
        wallet_with_hd = CryptoWallet(
            id=inserted_wallet.id,
            entity_id=inserted_wallet.entity_id,
            addresses=[],
            name="My BTC HD Wallet",
            address_source=AddressSource.DERIVED,
            hd_wallet=HDWallet(
                xpub=hd_wallet_args[1].xpub,
                addresses=[],
                script_type=hd_wallet_args[1].script_type,
                coin_type=hd_wallet_args[1].coin_type,
            ),
        )

        _setup_get_entities_mocks(
            entity_port,
            credentials_port,
            last_fetches_port,
            virtual_import_registry,
            entity_account_port,
            crypto_wallet_port,
            wallets_by_entity={uuid.UUID(BITCOIN_ID): [wallet_with_hd]},
        )
        get_resp = await client.get(GET_ENTITIES_URL)
        assert get_resp.status_code == 200
        entities_body = await get_resp.get_json()

        btc_entity = next(
            e for e in entities_body["entities"] if str(e["id"]) == BITCOIN_ID
        )
        assert len(btc_entity["connected"]) == 1
        wallet = btc_entity["connected"][0]
        assert wallet["name"] == "My BTC HD Wallet"
        assert wallet["address_source"] == "DERIVED"
        assert wallet["hd_wallet"] is not None
        assert wallet["hd_wallet"]["xpub"] == "xpub6CatV..."

    @pytest.mark.asyncio
    async def test_connect_derived_xpub_already_exists(
        self,
        client,
        crypto_wallet_port,
    ):
        crypto_wallet_port.exists_by_entity_and_xpub = AsyncMock(return_value=True)
        response = await client.post(
            CONNECT_URL,
            json={
                "entityId": BITCOIN_ID,
                "addresses": [],
                "name": "My BTC HD Wallet",
                "source": "DERIVED",
                "xpub": "xpub6CatV...",
                "script_type": "p2wpkh",
            },
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert "xpub6CatV..." in body["failed"]
        assert body["failed"]["xpub6CatV..."] == "XPUB_ALREADY_EXISTS"
        crypto_wallet_port.insert.assert_not_awaited()


class TestUpdateValidation:
    @pytest.mark.asyncio
    async def test_returns_400_on_empty_body(self, client):
        response = await client.put(UPDATE_URL, json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_id_missing(self, client):
        response = await client.put(
            UPDATE_URL,
            json={"name": "New Name"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_name_missing(self, client):
        wallet_id = str(uuid.uuid4())
        response = await client.put(
            UPDATE_URL,
            json={"id": wallet_id},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_uuid(self, client):
        response = await client.put(
            UPDATE_URL,
            json={"id": "not-a-uuid", "name": "New Name"},
        )
        assert response.status_code == 400
        body = await response.get_json()
        assert "format" in body["message"].lower()


class TestUpdateAndRead:
    @pytest.mark.asyncio
    async def test_update_then_name_reflected_in_entities(
        self,
        client,
        crypto_wallet_port,
        entity_port,
        credentials_port,
        last_fetches_port,
        virtual_import_registry,
        entity_account_port,
    ):
        wallet_id = uuid.uuid4()
        response = await client.put(
            UPDATE_URL,
            json={"id": str(wallet_id), "name": "Updated Wallet Name"},
        )
        assert response.status_code == 204
        crypto_wallet_port.rename.assert_awaited_once_with(
            wallet_id, "Updated Wallet Name"
        )

        # Verify renamed wallet appears in GET /entities
        renamed_wallet = CryptoWallet(
            id=wallet_id,
            entity_id=uuid.UUID(ETHEREUM_ID),
            addresses=["0xabc123"],
            name="Updated Wallet Name",
            address_source=AddressSource.MANUAL,
            hd_wallet=None,
        )
        _setup_get_entities_mocks(
            entity_port,
            credentials_port,
            last_fetches_port,
            virtual_import_registry,
            entity_account_port,
            crypto_wallet_port,
            wallets_by_entity={uuid.UUID(ETHEREUM_ID): [renamed_wallet]},
        )
        get_resp = await client.get(GET_ENTITIES_URL)
        assert get_resp.status_code == 200
        entities_body = await get_resp.get_json()

        eth_entity = next(
            e for e in entities_body["entities"] if str(e["id"]) == ETHEREUM_ID
        )
        assert len(eth_entity["connected"]) == 1
        assert eth_entity["connected"][0]["name"] == "Updated Wallet Name"


class TestDeleteValidation:
    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_uuid(self, client):
        response = await client.delete(_delete_url("not-a-uuid"))
        assert response.status_code == 400
        body = await response.get_json()
        assert "format" in body["message"].lower()


class TestDeleteAndRead:
    @pytest.mark.asyncio
    async def test_delete_then_wallet_gone_from_entities(
        self,
        client,
        crypto_wallet_port,
        entity_port,
        credentials_port,
        last_fetches_port,
        virtual_import_registry,
        entity_account_port,
    ):
        wallet_id = str(uuid.uuid4())
        response = await client.delete(_delete_url(wallet_id))
        assert response.status_code == 204
        crypto_wallet_port.delete.assert_awaited_once_with(uuid.UUID(wallet_id))

        # Verify wallet gone from GET /entities
        _setup_get_entities_mocks(
            entity_port,
            credentials_port,
            last_fetches_port,
            virtual_import_registry,
            entity_account_port,
            crypto_wallet_port,
            wallets_by_entity={},
        )
        get_resp = await client.get(GET_ENTITIES_URL)
        assert get_resp.status_code == 200
        entities_body = await get_resp.get_json()

        eth_entity = next(
            e for e in entities_body["entities"] if str(e["id"]) == ETHEREUM_ID
        )
        assert eth_entity["connected"] == []

        btc_entity = next(
            e for e in entities_body["entities"] if str(e["id"]) == BITCOIN_ID
        )
        assert btc_entity["connected"] == []


class TestGetAddressesValidation:
    @pytest.mark.asyncio
    async def test_returns_400_when_wallet_id_missing(self, client):
        response = await client.get(GET_ADDRESSES_URL)
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_uuid(self, client):
        response = await client.get(f"{GET_ADDRESSES_URL}?wallet_id=not-a-uuid")
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"


class TestGetAddresses:
    @pytest.mark.asyncio
    async def test_returns_404_when_wallet_not_found(self, client, crypto_wallet_port):
        crypto_wallet_port.get_by_id = AsyncMock(return_value=None)
        wallet_id = str(uuid.uuid4())
        response = await client.get(f"{GET_ADDRESSES_URL}?wallet_id={wallet_id}")
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_400_for_manual_wallet(self, client, crypto_wallet_port):
        wallet_id = uuid.uuid4()
        crypto_wallet_port.get_by_id = AsyncMock(
            return_value=CryptoWallet(
                id=wallet_id,
                entity_id=uuid.UUID(ETHEREUM_ID),
                addresses=["0xabc"],
                name="Manual Wallet",
                address_source=AddressSource.MANUAL,
                hd_wallet=None,
            )
        )
        response = await client.get(f"{GET_ADDRESSES_URL}?wallet_id={wallet_id}")
        assert response.status_code == 400
        body = await response.get_json()
        assert body["code"] == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_returns_addresses_for_derived_wallet(
        self, client, crypto_wallet_port
    ):
        wallet_id = uuid.uuid4()
        hd_addresses = [
            HDAddress(
                address="bc1qaddr0",
                index=0,
                change=0,
                path="m/84'/0'/0'/0/0",
                pubkey="pub0",
                balance=Dezimal("1.5"),
            ),
            HDAddress(
                address="bc1qaddr1",
                index=1,
                change=0,
                path="m/84'/0'/0'/0/1",
                pubkey="pub1",
                balance=Dezimal("0"),
            ),
            HDAddress(
                address="bc1qchange0",
                index=0,
                change=1,
                path="m/84'/0'/0'/1/0",
                pubkey="cpub0",
                balance=Dezimal("0.25"),
            ),
        ]
        crypto_wallet_port.get_by_id = AsyncMock(
            return_value=CryptoWallet(
                id=wallet_id,
                entity_id=uuid.UUID(BITCOIN_ID),
                addresses=[],
                name="HD Wallet",
                address_source=AddressSource.DERIVED,
                hd_wallet=HDWallet(
                    xpub="xpub6test123",
                    addresses=hd_addresses,
                    script_type=ScriptType.P2WPKH,
                    coin_type=CoinType.BITCOIN,
                ),
            )
        )

        response = await client.get(f"{GET_ADDRESSES_URL}?wallet_id={wallet_id}")
        assert response.status_code == 200
        body = await response.get_json()

        assert body["id"] == str(wallet_id)
        assert body["name"] == "HD Wallet"
        assert body["address_source"] == "DERIVED"
        assert body["hd_wallet"] is not None
        assert body["hd_wallet"]["xpub"] == "xpub6test123"
        assert body["hd_wallet"]["script_type"] == "p2wpkh"
        assert len(body["hd_wallet"]["receiving"]) == 2
        assert len(body["hd_wallet"]["change"]) == 1
        assert body["hd_wallet"]["receiving"][0]["address"] == "bc1qaddr0"
        assert body["hd_wallet"]["receiving"][0]["index"] == 0
        assert body["hd_wallet"]["receiving"][0]["path"] == "m/84'/0'/0'/0/0"
        assert body["hd_wallet"]["receiving"][0]["balance"] == 1.5
        assert body["hd_wallet"]["receiving"][1]["balance"] == 0
        assert body["hd_wallet"]["change"][0]["address"] == "bc1qchange0"
        assert body["hd_wallet"]["change"][0]["change"] == 1
        assert body["hd_wallet"]["change"][0]["balance"] == 0.25
