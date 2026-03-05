from unittest.mock import AsyncMock

import pytest
from uuid import UUID

from application.use_cases.derive_crypto_addresses import (
    DeriveCryptoAddressesImpl,
    ENTITY_TO_COIN_TYPE,
)
from application.ports.public_key_derivation import PublicKeyDerivation
from domain import native_entities
from domain.exception.exceptions import EntityNotFound
from domain.public_key import (
    AddressDerivationRequest,
    AddressDerivationPreviewRequest,
    DerivedAddressesResult,
    CoinType,
    ScriptType,
    DerivedAddress,
)


class MockPublicKeyDerivation(PublicKeyDerivation):
    def calculate(self, request: AddressDerivationRequest) -> DerivedAddressesResult:
        receiving = [
            DerivedAddress(
                index=i,
                path=f"m/44'/{request.coin.value}/0/{i}",
                address=f"address_receiving_{i}",
                pubkey=f"pubkey_receiving_{i}",
                change=0,
            )
            for i in range(request.receiving_range[0], request.receiving_range[1])
        ]

        change = [
            DerivedAddress(
                index=i,
                path=f"m/44'/{request.coin.value}/1/{i}",
                address=f"address_change_{i}",
                pubkey=f"pubkey_change_{i}",
                change=1,
            )
            for i in range(request.change_range[0], request.change_range[1])
        ]

        script_type = request.script_type or ScriptType.P2PKH

        return DerivedAddressesResult(
            key_type="xpub",
            script_type=script_type,
            coin=request.coin,
            receiving=receiving,
            change=change,
            base_path=f"m/44'/{request.coin.value}'/0'",
        )


class TestDeriveCryptoAddressesImpl:
    @pytest.fixture
    def mock_public_key_derivation(self):
        return MockPublicKeyDerivation()

    @pytest.fixture
    def mock_entity_port(self):
        port = AsyncMock()
        port.get_by_id = AsyncMock(return_value=None)
        port.get_all = AsyncMock(return_value=[])
        port.get_by_natural_id = AsyncMock(return_value=None)
        port.get_by_name = AsyncMock(return_value=None)
        port.get_disabled_entities = AsyncMock(return_value=[])
        return port

    @pytest.fixture
    def use_case(self, mock_public_key_derivation, mock_entity_port):
        return DeriveCryptoAddressesImpl(
            mock_public_key_derivation,
            mock_entity_port,
        )

    @pytest.mark.asyncio
    async def test_execute_with_bitcoin(self, use_case):
        request = AddressDerivationPreviewRequest(
            xpub="xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8",
            entity=native_entities.BITCOIN,
            range=5,
        )

        result = await use_case.execute(request)

        assert result.coin == CoinType.BITCOIN
        assert len(result.receiving) == 5
        assert len(result.change) == 5
        assert result.base_path == "m/44'/BITCOIN'/0'"

    @pytest.mark.asyncio
    async def test_execute_with_litecoin(self, use_case):
        request = AddressDerivationPreviewRequest(
            xpub="Ltub2SSUS19CirucVPBSjuRMt2SF9H93viG9rz4TkpzAEFjsxHXKjA3jFe1b91cgf2f5dVLrjjJDBTQaVQHMJvhPLiTFGZqPXBbPNxae12HPLLN",
            entity=native_entities.LITECOIN,
            range=10,
        )

        result = await use_case.execute(request)

        assert result.coin == CoinType.LITECOIN
        assert len(result.receiving) == 10
        assert len(result.change) == 10

    @pytest.mark.asyncio
    async def test_execute_with_custom_script_type(self, use_case):
        request = AddressDerivationPreviewRequest(
            xpub="zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs",
            entity=native_entities.BITCOIN,
            range=3,
            script_type=ScriptType.P2WPKH,
        )

        result = await use_case.execute(request)

        assert result.script_type == ScriptType.P2WPKH

    @pytest.mark.asyncio
    async def test_execute_with_ethereum_raises_value_error(self, use_case):
        request = AddressDerivationPreviewRequest(
            xpub="xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8",
            entity=native_entities.ETHEREUM,
            range=5,
        )

        with pytest.raises(ValueError, match="does not support address derivation"):
            await use_case.execute(request)


class TestGetCoinTypeFromEntityId:
    def test_bitcoin_entity_returns_bitcoin_coin_type(self):
        coin_type = DeriveCryptoAddressesImpl._get_coin_type_from_entity_id(
            native_entities.BITCOIN.id
        )

        assert coin_type == CoinType.BITCOIN

    def test_litecoin_entity_returns_litecoin_coin_type(self):
        coin_type = DeriveCryptoAddressesImpl._get_coin_type_from_entity_id(
            native_entities.LITECOIN.id
        )

        assert coin_type == CoinType.LITECOIN

    def test_ethereum_entity_raises_value_error(self):
        with pytest.raises(ValueError, match="does not support address derivation"):
            DeriveCryptoAddressesImpl._get_coin_type_from_entity_id(
                native_entities.ETHEREUM.id
            )

    def test_unknown_entity_raises_entity_not_found(self):
        unknown_id = UUID("00000000-0000-0000-0000-000000000999")

        with pytest.raises(EntityNotFound):
            DeriveCryptoAddressesImpl._get_coin_type_from_entity_id(unknown_id)

    def test_non_crypto_entity_raises_entity_not_found(self):
        with pytest.raises(EntityNotFound):
            DeriveCryptoAddressesImpl._get_coin_type_from_entity_id(
                native_entities.MY_INVESTOR.id
            )


class TestEntityToCoinTypeMapping:
    def test_bitcoin_entity_mapped(self):
        assert native_entities.BITCOIN.id in ENTITY_TO_COIN_TYPE
        assert ENTITY_TO_COIN_TYPE[native_entities.BITCOIN.id] == CoinType.BITCOIN

    def test_litecoin_entity_mapped(self):
        assert native_entities.LITECOIN.id in ENTITY_TO_COIN_TYPE
        assert ENTITY_TO_COIN_TYPE[native_entities.LITECOIN.id] == CoinType.LITECOIN
