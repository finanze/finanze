from uuid import UUID

from application.ports.crypto_wallet_port import CryptoWalletPort
from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection


class DeleteCryptoWalletConnectionImpl(DeleteCryptoWalletConnection):
    def __init__(
        self,
        crypto_wallet_port: CryptoWalletPort,
    ):
        self._crypto_wallet_port = crypto_wallet_port

    async def execute(self, wallet_connection_id: UUID):
        await self._crypto_wallet_port.delete(wallet_connection_id)
