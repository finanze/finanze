from uuid import uuid4

from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from domain import native_entities
from domain.crypto import ConnectCryptoWallet as ConnectCryptoWalletRequest
from domain.crypto import CryptoWalletConnection
from domain.entity import EntityType
from domain.exception.exceptions import EntityNotFound
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet


class ConnectCryptoWalletImpl(ConnectCryptoWallet):
    def __init__(
        self,
        crypto_wallet_connections_port: CryptoWalletConnectionPort,
    ):
        self._crypto_wallet_connections_port = crypto_wallet_connections_port

    def execute(self, request: ConnectCryptoWalletRequest):
        entity_id = request.entity_id

        entity = native_entities.get_native_by_id(entity_id, EntityType.CRYPTO_WALLET)
        if not entity:
            raise EntityNotFound(entity_id)

        existing_wallet = self._crypto_wallet_connections_port.get_by_address(
            request.address
        )
        if existing_wallet:
            raise ValueError(f"Wallet with address {request.address} already exists")

        wallet = CryptoWalletConnection(
            id=uuid4(),
            entity_id=request.entity_id,
            address=request.address,
            name=request.name,
        )
        self._crypto_wallet_connections_port.insert(wallet)
