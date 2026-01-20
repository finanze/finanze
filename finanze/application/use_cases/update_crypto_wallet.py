from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from domain.crypto import (
    UpdateCryptoWalletConnection as UpdateCryptoWalletConnectionRequest,
)
from domain.use_cases.update_crypto_wallet import UpdateCryptoWalletConnection


class UpdateCryptoWalletConnectionImpl(UpdateCryptoWalletConnection):
    def __init__(self, crypto_wallet_connections_port: CryptoWalletConnectionPort):
        self._crypto_wallet_connections_port = crypto_wallet_connections_port

    async def execute(self, data: UpdateCryptoWalletConnectionRequest):
        await self._crypto_wallet_connections_port.rename(data.id, data.name)
