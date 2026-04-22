from uuid import UUID

from application.ports.crypto_wallet_port import CryptoWalletPort
from domain.crypto import CryptoWallet, AddressSource
from domain.exception.exceptions import EntityNotFound
from domain.use_cases.get_crypto_wallet_addresses import GetCryptoWalletAddresses


class GetCryptoWalletAddressesImpl(GetCryptoWalletAddresses):
    def __init__(self, crypto_wallet_port: CryptoWalletPort):
        self._crypto_wallet_port = crypto_wallet_port

    async def execute(self, wallet_id: UUID) -> CryptoWallet:
        wallet = await self._crypto_wallet_port.get_by_id(wallet_id)
        if not wallet:
            raise EntityNotFound()
        if wallet.address_source != AddressSource.DERIVED:
            raise ValueError("Wallet is not a derived wallet")
        return wallet
