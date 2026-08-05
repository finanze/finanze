from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.crypto_wallet_port import CryptoWalletPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.position_snapshot_ids import regenerate_snapshot_ids
from domain.fetch_record import DataSource
from domain.global_position import CryptoCurrencies, PositionQueryRequest, ProductType
from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection


class DeleteCryptoWalletConnectionImpl(DeleteCryptoWalletConnection, AtomicUCMixin):
    def __init__(
        self,
        crypto_wallet_port: CryptoWalletPort,
        position_port: PositionPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._crypto_wallet_port = crypto_wallet_port
        self._position_port = position_port

    async def _save_positions_without_wallet(
        self, wallet_connection_id: UUID, entity_id: UUID
    ):
        positions_by_entity = await self._position_port.get_last_by_entity_broken_down(
            PositionQueryRequest(entities=[entity_id], real=True)
        )
        current_positions = next(
            (
                positions
                for entity, positions in positions_by_entity.items()
                if entity.id == entity_id
            ),
            [],
        )

        for position in current_positions:
            crypto_positions = position.products.get(ProductType.CRYPTO)
            if not isinstance(crypto_positions, CryptoCurrencies):
                continue
            if not any(
                wallet.id == wallet_connection_id for wallet in crypto_positions.entries
            ):
                continue

            corrected_position = deepcopy(position)
            corrected_crypto_positions = corrected_position.products[ProductType.CRYPTO]
            corrected_crypto_positions.entries = [
                wallet
                for wallet in corrected_crypto_positions.entries
                if wallet.id != wallet_connection_id
            ]
            corrected_position.id = uuid4()
            corrected_position.date = datetime.now().astimezone()
            corrected_position.source = DataSource.REAL
            regenerate_snapshot_ids(corrected_position)
            await self._position_port.save(corrected_position)

    async def execute(self, wallet_connection_id: UUID):
        wallet = await self._crypto_wallet_port.get_by_id(wallet_connection_id)
        if wallet:
            await self._save_positions_without_wallet(
                wallet_connection_id, wallet.entity_id
            )
        await self._crypto_wallet_port.delete(wallet_connection_id)
