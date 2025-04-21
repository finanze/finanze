import logging

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.credentials_port import CredentialsPort
from application.ports.entity_scraper import EntityScraper
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain import native_entities
from domain.exception.exceptions import EntityNotFound, InvalidProvidedCredentials
from domain.financial_entity import FinancialEntity
from domain.login import LoginResultCode, LoginResult, LoginRequest, LoginParams, LoginOptions
from domain.use_cases.add_entity_credentials import AddEntityCredentials


class AddEntityCredentialsImpl(AtomicUCMixin, AddEntityCredentials):

    def __init__(self,
                 entity_scrapers: dict[FinancialEntity, EntityScraper],
                 credentials_port: CredentialsPort,
                 sessions_port: SessionsPort,
                 transaction_handler_port: TransactionHandlerPort):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._entity_scrapers = entity_scrapers
        self._credentials_port = credentials_port
        self._sessions_port = sessions_port

        self._log = logging.getLogger(__name__)

    async def execute(self,
                      login_request: LoginRequest) -> LoginResult:

        entity_id = login_request.entity_id

        entity = native_entities.get_native_by_id(entity_id)
        if not entity:
            raise EntityNotFound(entity_id)

        credentials = login_request.credentials

        for cred_name in entity.credentials_template.keys():
            if cred_name not in credentials:
                raise InvalidProvidedCredentials()

        specific_scraper = self._entity_scrapers[entity]

        login_options = LoginOptions(
            avoid_new_login=False,
            force_new_session=True
        )

        login_request = LoginParams(
            credentials=credentials,
            two_factor=login_request.two_factor,
            options=login_options,
        )
        login_result = await specific_scraper.login(login_request)
        if login_result.code != LoginResultCode.CREATED:
            return login_result

        self._credentials_port.delete(entity.id)
        self._credentials_port.save(entity.id, credentials)

        self._sessions_port.delete(entity.id)
        session = login_result.session
        if session:
            self._sessions_port.save(entity.id, session)

        return LoginResult(LoginResultCode.CREATED)
