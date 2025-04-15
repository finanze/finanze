import logging

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.credentials_port import CredentialsPort
from application.ports.entity_scraper import EntityScraper
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain import native_entities
from domain.exception.exceptions import EntityNotFound, InvalidProvidedCredentials
from domain.financial_entity import FinancialEntity
from domain.login_result import LoginResultCode, LoginResult, LoginRequest, LoginParams
from domain.use_cases.add_entity_credentials import AddEntityCredentials


class AddEntityCredentialsImpl(AtomicUCMixin, AddEntityCredentials):

    def __init__(self,
                 entity_scrapers: dict[FinancialEntity, EntityScraper],
                 credentials_port: CredentialsPort,
                 transaction_handler_port: TransactionHandlerPort):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._entity_scrapers = entity_scrapers
        self._credentials_port = credentials_port

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

        # TODO: Clear stored session
        login_request = LoginParams(
            credentials=credentials,
            two_factor=login_request.two_factor,
            options=login_request.options
        )
        login_result = await specific_scraper.login(login_request)
        login_result_code = login_result["result"]
        del login_result["result"]

        if login_result_code == LoginResultCode.CODE_REQUESTED:
            return LoginResult(LoginResultCode.CODE_REQUESTED, details=login_result)

        elif login_result_code != LoginResultCode.CREATED:
            return LoginResult(login_result_code, details=login_result)

        existing_credentials = self._credentials_port.get(entity_id)
        if existing_credentials:
            self._credentials_port.delete(entity_id)

        self._credentials_port.save(entity_id, credentials)

        return LoginResult(LoginResultCode.CREATED)
