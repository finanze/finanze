import logging
from datetime import datetime
from uuid import uuid4

from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from application.ports.public_keychain_loader import PublicKeychainLoader
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from dateutil.tz import tzlocal
from domain import native_entities
from domain.entity import Entity, EntityType
from domain.entity_account import EntityAccount
from domain.native_entity import CredentialType, NativeCryptoExchangeEntity
from domain.entity_login import (
    EntityLoginParams,
    EntityLoginRequest,
    EntityLoginResult,
    LoginOptions,
    LoginResultCode,
)
from domain.exception.exceptions import EntityNotFound, InvalidProvidedCredentials
from domain.use_cases.add_entity_credentials import AddEntityCredentials


class AddEntityCredentialsImpl(AddEntityCredentials):
    def __init__(
        self,
        entity_fetchers: dict[Entity, FinancialEntityFetcher],
        credentials_port: CredentialsPort,
        sessions_port: SessionsPort,
        transaction_handler_port: TransactionHandlerPort,
        keychain_loader: PublicKeychainLoader,
        entity_account_port: EntityAccountPort,
    ):
        self._entity_fetchers = entity_fetchers
        self._credentials_port = credentials_port
        self._sessions_port = sessions_port
        self._keychain_loader = keychain_loader
        self._transaction_handler_port = transaction_handler_port
        self._entity_account_port = entity_account_port

        self._log = logging.getLogger(__name__)

    async def execute(self, login_request: EntityLoginRequest) -> EntityLoginResult:
        entity_id = login_request.entity_id

        entity = native_entities.get_native_by_id(
            entity_id, EntityType.FINANCIAL_INSTITUTION, EntityType.CRYPTO_EXCHANGE
        )
        if not entity:
            raise EntityNotFound(entity_id)

        credentials = login_request.credentials

        for cred_name, cred_type in entity.credentials_template.items():
            if (
                cred_type != CredentialType.INTERNAL
                and cred_type != CredentialType.INTERNAL_TEMP
                and cred_name not in credentials
            ):
                raise InvalidProvidedCredentials()

        specific_fetcher = self._entity_fetchers[entity]

        keychain = await self._keychain_loader.load()

        login_options = LoginOptions(avoid_new_login=False, force_new_session=True)

        login_params = EntityLoginParams(
            credentials=credentials,
            two_factor=login_request.two_factor,
            options=login_options,
            keychain=keychain,
        )
        login_result = await specific_fetcher.login(login_params)
        if login_result.code != LoginResultCode.CREATED:
            return login_result

        is_crypto_exchange = isinstance(entity, NativeCryptoExchangeEntity)
        entity_account_id = login_request.entity_account_id

        async with self._transaction_handler_port.start():
            if entity_account_id:
                # Re-login for existing account: replace credentials and session
                await self._credentials_port.delete(entity_account_id)
                await self._sessions_port.delete(entity_account_id)
            else:
                if is_crypto_exchange:
                    # New account for crypto exchange
                    entity_account_id = uuid4()
                    account = EntityAccount(
                        id=entity_account_id,
                        entity_id=entity.id,
                        created_at=datetime.now(tzlocal()),
                        name=login_request.account_name,
                    )
                    await self._entity_account_port.create(account)
                else:
                    # Financial institution: get existing account or create one
                    existing_accounts = (
                        await self._entity_account_port.get_by_entity_id(entity.id)
                    )
                    if existing_accounts:
                        entity_account_id = existing_accounts[0].id
                        await self._credentials_port.delete(entity_account_id)
                        await self._sessions_port.delete(entity_account_id)
                    else:
                        entity_account_id = uuid4()
                        account = EntityAccount(
                            id=entity_account_id,
                            entity_id=entity.id,
                            created_at=datetime.now(tzlocal()),
                            name=login_request.account_name,
                        )
                        await self._entity_account_port.create(account)

            credentials_to_store = {
                k: v
                for k, v in credentials.items()
                if entity.credentials_template[k] != CredentialType.INTERNAL_TEMP
            }
            await self._credentials_port.save(
                entity_account_id, entity.id, credentials_to_store
            )

            session = login_result.session
            if session:
                await self._sessions_port.save(entity_account_id, entity.id, session)

            return EntityLoginResult(
                LoginResultCode.CREATED, entity_account_id=entity_account_id
            )
