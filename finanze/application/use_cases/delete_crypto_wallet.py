from uuid import UUID

from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection


class DeleteCryptoWalletConnectionImpl(DeleteCryptoWalletConnection):
    def __init__(
        self,
        crypto_wallet_connections_port: CryptoWalletConnectionPort,
    ):
        self._crypto_wallet_connections_port = crypto_wallet_connections_port

    async def execute(self, wallet_connection_id: UUID):
        await self._crypto_wallet_connections_port.delete(wallet_connection_id)
