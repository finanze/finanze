import logging

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.credentials_port import CredentialsPort
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
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
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._credentials_port = credentials_port
        self._sessions_port = sessions_port

        self._log = logging.getLogger(__name__)

    async def execute(self, request: EntityDisconnectRequest):
        entity_id = request.entity_id

        entity = native_entities.get_native_by_id(
            entity_id, EntityType.FINANCIAL_INSTITUTION, EntityType.CRYPTO_EXCHANGE
        )
        if not entity:
            raise EntityNotFound(entity_id)

        await self._credentials_port.delete(entity_id)
        await self._sessions_port.delete(entity_id)
