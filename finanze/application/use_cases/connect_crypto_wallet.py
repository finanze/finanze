from logging import Logger
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
    CryptoWalletConnectionFailureCode,
    CryptoWalletConnectionResult,
)
from domain.entity import Entity, EntityType
from domain.exception.exceptions import (
    AddressNotFound,
    EntityNotFound,
    TooManyRequests,
)
from domain.external_integration import EtherscanIntegrationData
from domain.settings import IntegrationsConfig
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet


def from_config(config: IntegrationsConfig):
    etherscan = None
    if config.etherscan:
        etherscan = EtherscanIntegrationData(config.etherscan.api_key)
    return CryptoFetchIntegrations(etherscan=etherscan)


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

        self._log = Logger(__name__)

    def execute(
        self, request: ConnectCryptoWalletRequest
    ) -> CryptoWalletConnectionResult:
        entity_id = request.entity_id

        entity = native_entities.get_native_by_id(entity_id, EntityType.CRYPTO_WALLET)
        if not entity:
            raise EntityNotFound(entity_id)

        integrations = from_config(self._config_port.load().integrations)

        failed_addresses = {}

        specific_fetcher = self._entity_fetchers[entity]

        name_counter = 1

        for address in request.addresses:
            existing_wallet = (
                self._crypto_wallet_connections_port.get_by_entity_and_address(
                    entity_id, address
                )
            )
            if existing_wallet:
                failed_addresses[address] = (
                    CryptoWalletConnectionFailureCode.ADDRESS_ALREADY_EXISTS
                )
                continue

            try:
                specific_fetcher.fetch(
                    CryptoFetchRequest(address=address, integrations=integrations)
                )

                if name_counter == 1:
                    wallet_name = request.name
                else:
                    wallet_name = f"{request.name} {name_counter}"

                wallet = CryptoWalletConnection(
                    id=uuid4(),
                    entity_id=request.entity_id,
                    address=address,
                    name=wallet_name,
                )
                self._crypto_wallet_connections_port.insert(wallet)

                name_counter += 1

            except AddressNotFound:
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

        return CryptoWalletConnectionResult(failed=failed_addresses)
