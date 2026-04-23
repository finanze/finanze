import logging

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from application.ports.historic_port import HistoricPort
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from domain import native_entities
from domain.entity import EntityType
from domain.entity_login import EntityDisconnectRequest
from domain.exception.exceptions import EntityNotFound
from domain.use_cases.disconnect_entity import DisconnectEntity


class DisconnectEntityImpl(AtomicUCMixin, DisconnectEntity):
    def __init__(
        self,
        credentials_port: CredentialsPort,
        sessions_port: SessionsPort,
        transaction_handler_port: TransactionHandlerPort,
        entity_account_port: EntityAccountPort,
        transaction_port: TransactionPort,
        auto_contributions_port: AutoContributionsPort,
        historic_port: HistoricPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._credentials_port = credentials_port
        self._sessions_port = sessions_port
        self._entity_account_port = entity_account_port
        self._transaction_port = transaction_port
        self._auto_contributions_port = auto_contributions_port
        self._historic_port = historic_port

        self._log = logging.getLogger(__name__)

    async def execute(self, request: EntityDisconnectRequest):
        entity_account_id = request.entity_account_id

        entity_account = await self._entity_account_port.get_by_id(entity_account_id)
        if not entity_account:
            raise EntityNotFound(entity_account_id)

        entity_id = entity_account.entity_id

        entity = native_entities.get_native_by_id(
            entity_id, EntityType.FINANCIAL_INSTITUTION, EntityType.CRYPTO_EXCHANGE
        )
        if not entity:
            raise EntityNotFound(entity_id)

        is_crypto_exchange = entity.type == EntityType.CRYPTO_EXCHANGE

        if is_crypto_exchange:
            # Disconnect single crypto exchange account
            await self._credentials_port.delete(entity_account_id)
            await self._sessions_port.delete(entity_account_id)
            await self._entity_account_port.soft_delete(entity_account_id)
        else:
            # Disconnect all accounts for the entity (FI only has one)
            await self._credentials_port.delete_by_entity_id(entity_id)
            await self._sessions_port.delete_by_entity_id(entity_id)
            await self._entity_account_port.soft_delete_by_entity_id(entity_id)

        await self._transaction_port.delete_by_entity_account_id(entity_account_id)
        await self._auto_contributions_port.delete_by_entity_account_id(
            entity_account_id
        )
        await self._historic_port.delete_by_entity_account_id(entity_account_id)
