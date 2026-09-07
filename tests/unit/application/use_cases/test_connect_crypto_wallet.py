from unittest.mock import AsyncMock, MagicMock

import pytest

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_wallet_port import CryptoWalletPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.public_key_derivation import PublicKeyDerivation
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.connect_crypto_wallet import ConnectCryptoWalletImpl
from domain import native_entities
from domain.crypto import (
    AddressSource,
    ConnectCryptoWallet,
    CryptoCurrencyType,
    CryptoFetchedPosition,
    CryptoFetchResult,
    CryptoFetchResults,
    CryptoWalletConnectionFailureCode,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExternalIntegrationRequired, TooManyRequests
from domain.external_integration import ExternalIntegrationId

ZERION_ENTITY = native_entities.ZERION
FAKE_ADDRESS = "0xfake00000000000000000000000000000000c001"


def _request():
    return ConnectCryptoWallet(
        entity_id=ZERION_ENTITY.id,
        addresses=[FAKE_ADDRESS],
        name="DeFi wallet",
        address_source=AddressSource.MANUAL,
    )


def _found_results(address):
    return CryptoFetchResults(
        results={
            address: CryptoFetchResult(
                address=address,
                assets=[
                    CryptoFetchedPosition(
                        id=None,
                        symbol="ETH",
                        balance=Dezimal("0.5"),
                        type=CryptoCurrencyType.NATIVE,
                        chain="ethereum",
                    )
                ],
            )
        }
    )


@pytest.fixture
def wallet_port():
    port = AsyncMock(spec=CryptoWalletPort)
    port.exists_by_entity_and_address.return_value = False
    return port


@pytest.fixture
def fetcher():
    return AsyncMock(spec=CryptoEntityFetcher)


@pytest.fixture
def use_case(wallet_port, fetcher):
    ext_int_port = AsyncMock(spec=ExternalIntegrationPort)
    ext_int_port.get_payloads_by_type.return_value = {}
    tx_handler = MagicMock(spec=TransactionHandlerPort)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    tx_handler.start = MagicMock(return_value=transaction)
    return ConnectCryptoWalletImpl(
        wallet_port,
        {ZERION_ENTITY: fetcher},
        ext_int_port,
        MagicMock(spec=PublicKeyDerivation),
        tx_handler,
    )


class TestConnectManualWallet:
    @pytest.mark.asyncio
    async def test_missing_integration_propagates_as_structured_error(
        self, use_case, wallet_port, fetcher
    ):
        fetcher.fetch.side_effect = ExternalIntegrationRequired(
            [ExternalIntegrationId.ZERION]
        )

        with pytest.raises(ExternalIntegrationRequired) as exc_info:
            await use_case.execute(_request())

        assert exc_info.value.required_integrations == [ExternalIntegrationId.ZERION]
        wallet_port.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_too_many_requests_maps_to_failure_code(
        self, use_case, wallet_port, fetcher
    ):
        fetcher.fetch.side_effect = TooManyRequests()

        result = await use_case.execute(_request())

        assert result.failed == {
            FAKE_ADDRESS: CryptoWalletConnectionFailureCode.TOO_MANY_REQUESTS
        }
        wallet_port.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unexpected_error_maps_to_failure_code(
        self, use_case, wallet_port, fetcher
    ):
        fetcher.fetch.side_effect = RuntimeError("provider exploded")

        result = await use_case.execute(_request())

        assert result.failed == {
            FAKE_ADDRESS: CryptoWalletConnectionFailureCode.UNEXPECTED_ERROR
        }
        wallet_port.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_found_address_inserts_wallet(self, use_case, wallet_port, fetcher):
        fetcher.fetch.return_value = _found_results(FAKE_ADDRESS)

        result = await use_case.execute(_request())

        assert result.failed == {}
        wallet_port.insert.assert_awaited_once()
        inserted = wallet_port.insert.await_args.args[0]
        assert inserted.entity_id == ZERION_ENTITY.id
        assert inserted.addresses == [FAKE_ADDRESS]
        assert inserted.address_source == AddressSource.MANUAL
