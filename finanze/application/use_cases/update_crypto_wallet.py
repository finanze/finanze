from application.ports.crypto_wallet_port import CryptoWalletPort
from domain.crypto import (
    UpdateCryptoWalletConnection as UpdateCryptoWalletConnectionRequest,
)
from domain.use_cases.update_crypto_wallet import UpdateCryptoWalletConnection


class UpdateCryptoWalletConnectionImpl(UpdateCryptoWalletConnection):
    def __init__(self, crypto_wallet_port: CryptoWalletPort):
        self._crypto_wallet_port = crypto_wallet_port

    async def execute(self, data: UpdateCryptoWalletConnectionRequest):
        await self._crypto_wallet_port.rename(data.id, data.name)
