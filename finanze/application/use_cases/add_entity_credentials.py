import logging

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.credentials_port import CredentialsPort
from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain import native_entities
from domain.entity import CredentialType, Entity, EntityType
from domain.entity_login import (
    EntityLoginParams,
    EntityLoginRequest,
    EntityLoginResult,
    LoginOptions,
    LoginResultCode,
)
from domain.exception.exceptions import EntityNotFound, InvalidProvidedCredentials
from domain.use_cases.add_entity_credentials import AddEntityCredentials


class AddEntityCredentialsImpl(AtomicUCMixin, AddEntityCredentials):
    def __init__(
        self,
        entity_fetchers: dict[Entity, FinancialEntityFetcher],
        credentials_port: CredentialsPort,
        sessions_port: SessionsPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._entity_fetchers = entity_fetchers
        self._credentials_port = credentials_port
        self._sessions_port = sessions_port

        self._log = logging.getLogger(__name__)

    async def execute(self, login_request: EntityLoginRequest) -> EntityLoginResult:
        entity_id = login_request.entity_id

        entity = native_entities.get_native_by_id(
            entity_id, EntityType.FINANCIAL_INSTITUTION
        )
        if not entity:
            raise EntityNotFound(entity_id)

        if entity.type != EntityType.FINANCIAL_INSTITUTION:
            raise ValueError(f"Invalid entity type: {entity.type}")

        credentials = login_request.credentials

        for cred_name, cred_type in entity.credentials_template.items():
            if (
                cred_type != CredentialType.INTERNAL
                and cred_type != CredentialType.INTERNAL_TEMP
                and cred_name not in credentials
            ):
                raise InvalidProvidedCredentials()

        specific_fetcher = self._entity_fetchers[entity]

        login_options = LoginOptions(avoid_new_login=False, force_new_session=True)

        login_request = EntityLoginParams(
            credentials=credentials,
            two_factor=login_request.two_factor,
            options=login_options,
        )
        login_result = await specific_fetcher.login(login_request)
        if login_result.code != LoginResultCode.CREATED:
            return login_result

        self._credentials_port.delete(entity.id)

        credentials_to_store = {
            k: v
            for k, v in credentials.items()
            if entity.credentials_template[k] != CredentialType.INTERNAL_TEMP
        }
        self._credentials_port.save(entity.id, credentials_to_store)

        self._sessions_port.delete(entity.id)
        session = login_result.session
        if session:
            self._sessions_port.save(entity.id, session)

        return EntityLoginResult(LoginResultCode.CREATED)
