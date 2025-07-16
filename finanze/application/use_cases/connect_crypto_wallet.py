from uuid import uuid4

from application.ports.config_port import ConfigPort
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from domain import native_entities
from domain.crypto import (
    ConnectCryptoWallet as ConnectCryptoWalletRequest,
)
from domain.crypto import (
    CryptoFetchIntegrations,
    CryptoFetchRequest,
    CryptoWalletConnection,
)
from domain.entity import Entity, EntityType
from domain.exception.exceptions import AddressAlreadyExists, EntityNotFound
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet


class ConnectCryptoWalletImpl(ConnectCryptoWallet):
    def __init__(
        self,
        crypto_wallet_connections_port: CryptoWalletConnectionPort,
        entity_fetchers: dict[Entity, CryptoEntityFetcher],
        config_port: ConfigPort,
    ):
        self._crypto_wallet_connections_port = crypto_wallet_connections_port
        self._entity_fetchers = entity_fetchers
        self._config_port = config_port

    def execute(self, request: ConnectCryptoWalletRequest):
        entity_id = request.entity_id

        entity = native_entities.get_native_by_id(entity_id, EntityType.CRYPTO_WALLET)
        if not entity:
            raise EntityNotFound(entity_id)

        existing_wallet = (
            self._crypto_wallet_connections_port.get_by_entity_and_address(
                request.entity_id, request.address
            )
        )
        if existing_wallet:
            raise AddressAlreadyExists(
                f"Wallet with address {request.address} already exists"
            )

        integrations = CryptoFetchIntegrations.from_config(
            self._config_port.load().integrations
        )

        specific_fetcher = self._entity_fetchers[entity]
        specific_fetcher.fetch(
            CryptoFetchRequest(address=request.address, integrations=integrations)
        )

        wallet = CryptoWalletConnection(
            id=uuid4(),
            entity_id=request.entity_id,
            address=request.address,
            name=request.name,
        )
        self._crypto_wallet_connections_port.insert(wallet)
