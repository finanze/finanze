import uuid
from unittest.mock import AsyncMock

import pytest

from application.use_cases.get_crypto_wallet_addresses import (
    GetCryptoWalletAddressesImpl,
)
from domain.crypto import AddressSource, CryptoWallet, HDWallet, HDAddress
from domain.exception.exceptions import EntityNotFound
from domain.public_key import ScriptType, CoinType


@pytest.fixture
def crypto_wallet_port():
    return AsyncMock()


@pytest.fixture
def use_case(crypto_wallet_port):
    return GetCryptoWalletAddressesImpl(crypto_wallet_port)


class TestGetCryptoWalletAddresses:
    @pytest.mark.asyncio
    async def test_raises_entity_not_found_when_wallet_missing(
        self, use_case, crypto_wallet_port
    ):
        crypto_wallet_port.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(EntityNotFound):
            await use_case.execute(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_value_error_for_manual_wallet(
        self, use_case, crypto_wallet_port
    ):
        wallet = CryptoWallet(
            id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            addresses=["0xabc"],
            name="Manual",
            address_source=AddressSource.MANUAL,
            hd_wallet=None,
        )
        crypto_wallet_port.get_by_id = AsyncMock(return_value=wallet)
        with pytest.raises(ValueError, match="not a derived wallet"):
            await use_case.execute(wallet.id)

    @pytest.mark.asyncio
    async def test_returns_wallet_for_derived(self, use_case, crypto_wallet_port):
        wallet_id = uuid.uuid4()
        hd = HDWallet(
            xpub="xpub6test",
            addresses=[
                HDAddress(
                    address="bc1q1",
                    index=0,
                    change=0,
                    path="m/84'/0'/0'/0/0",
                    pubkey="pk0",
                ),
            ],
            script_type=ScriptType.P2WPKH,
            coin_type=CoinType.BITCOIN,
        )
        wallet = CryptoWallet(
            id=wallet_id,
            entity_id=uuid.uuid4(),
            addresses=[],
            name="HD",
            address_source=AddressSource.DERIVED,
            hd_wallet=hd,
        )
        crypto_wallet_port.get_by_id = AsyncMock(return_value=wallet)
        result = await use_case.execute(wallet_id)
        assert result.id == wallet_id
        assert result.hd_wallet is not None
        assert len(result.hd_wallet.addresses) == 1
        crypto_wallet_port.get_by_id.assert_awaited_once_with(wallet_id)
