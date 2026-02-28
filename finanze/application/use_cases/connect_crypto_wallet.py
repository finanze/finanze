from logging import Logger
from uuid import uuid4

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_wallet_port import CryptoWalletPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.public_key_derivation import PublicKeyDerivation
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.derive_crypto_addresses import get_coin_type_from_entity_id
from domain import native_entities
from domain.crypto import (
    ConnectCryptoWallet as ConnectCryptoWalletRequest,
    AddressSource,
)
from domain.crypto import (
    CryptoFetchRequest,
    CryptoWallet,
    CryptoWalletConnectionFailureCode,
    CryptoWalletConnectionResult,
    HDWallet,
)
from domain.entity import Entity, EntityType
from domain.exception.exceptions import (
    EntityNotFound,
    TooManyRequests,
)
from domain.external_integration import (
    ExternalIntegrationType,
)
from domain.native_entity import NativeCryptoWalletEntity
from domain.public_key import AddressDerivationRequest
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet


class ConnectCryptoWalletImpl(ConnectCryptoWallet):
    def __init__(
        self,
        crypto_wallet_port: CryptoWalletPort,
        entity_fetchers: dict[Entity, CryptoEntityFetcher],
        external_integration_port: ExternalIntegrationPort,
        public_key_derivation: PublicKeyDerivation,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._crypto_wallet_port = crypto_wallet_port
        self._entity_fetchers = entity_fetchers
        self._external_integration_port = external_integration_port
        self._public_key_derivation = public_key_derivation
        self._transaction_handler_port = transaction_handler_port

        self._log = Logger(__name__)

    async def execute(
        self, request: ConnectCryptoWalletRequest
    ) -> CryptoWalletConnectionResult:
        entity_id = request.entity_id

        entity = native_entities.get_native_by_id(entity_id, EntityType.CRYPTO_WALLET)
        if not entity:
            raise EntityNotFound(entity_id)

        if request.address_source == AddressSource.MANUAL:
            return await self._connect_manual(entity, request)
        else:
            return await self._connect_derived(entity, request)

    async def _connect_manual(
        self, entity: NativeCryptoWalletEntity, request: ConnectCryptoWalletRequest
    ) -> CryptoWalletConnectionResult:
        enabled_integrations = (
            await self._external_integration_port.get_payloads_by_type(
                ExternalIntegrationType.CRYPTO_PROVIDER
            )
        )

        failed_addresses = {}
        specific_fetcher = self._entity_fetchers[entity]

        for address in request.addresses:
            existing_wallet = (
                await self._crypto_wallet_port.exists_by_entity_and_address(
                    entity.id, address
                )
            )
            if existing_wallet:
                failed_addresses[address] = (
                    CryptoWalletConnectionFailureCode.ADDRESS_ALREADY_EXISTS
                )

        if failed_addresses:
            return CryptoWalletConnectionResult(failed=failed_addresses)

        for address in request.addresses:
            try:
                result = await specific_fetcher.fetch(
                    CryptoFetchRequest(
                        addresses=[address], integrations=enabled_integrations
                    )
                )
                if (
                    not result.results
                    or address not in result.results
                    or not result.results[address]
                ):
                    failed_addresses[address] = (
                        CryptoWalletConnectionFailureCode.ADDRESS_NOT_FOUND
                    )
            except TooManyRequests:
                failed_addresses[address] = (
                    CryptoWalletConnectionFailureCode.TOO_MANY_REQUESTS
                )
            except Exception as e:
                self._log.exception(e)
                failed_addresses[address] = (
                    CryptoWalletConnectionFailureCode.UNEXPECTED_ERROR
                )

        if failed_addresses:
            return CryptoWalletConnectionResult(failed=failed_addresses)

        wallet = CryptoWallet(
            id=uuid4(),
            entity_id=request.entity_id,
            addresses=request.addresses,
            address_source=AddressSource.MANUAL,
            name=request.name,
            hd_wallet=None,
        )

        async with self._transaction_handler_port.start():
            await self._crypto_wallet_port.insert(wallet)

        return CryptoWalletConnectionResult(failed={})

    async def _connect_derived(
        self, entity: NativeCryptoWalletEntity, request: ConnectCryptoWalletRequest
    ) -> CryptoWalletConnectionResult:
        if await self._crypto_wallet_port.exists_by_entity_and_xpub(
            entity.id, request.xpub
        ):
            return CryptoWalletConnectionResult(
                failed={
                    request.xpub: CryptoWalletConnectionFailureCode.XPUB_ALREADY_EXISTS
                }
            )

        coin_type = get_coin_type_from_entity_id(entity.id)

        derivation_request = AddressDerivationRequest(
            xpub=request.xpub,
            coin=coin_type,
            receiving_range=(0, 1),
            change_range=(0, 1),
            script_type=request.script_type,
            account=request.account,
        )

        derived_result = self._public_key_derivation.calculate(derivation_request)

        wallet_id = uuid4()

        wallet = CryptoWallet(
            id=wallet_id,
            entity_id=request.entity_id,
            addresses=[],
            address_source=AddressSource.DERIVED,
            name=request.name,
            hd_wallet=None,
        )

        hd_wallet = HDWallet(
            xpub=request.xpub,
            addresses=[],
            script_type=derived_result.script_type,
            coin_type=derived_result.coin,
            account=request.account,
        )

        async with self._transaction_handler_port.start():
            await self._crypto_wallet_port.insert(wallet)
            await self._crypto_wallet_port.insert_hd_wallet(wallet_id, hd_wallet)

        return CryptoWalletConnectionResult(failed={})
