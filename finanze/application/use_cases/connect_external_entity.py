import logging
from asyncio import Lock
from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.file_storage_port import FileStoragePort
from application.use_cases.fetch_external_financial_data import (
    external_entity_provider_integrations_from_config,
)
from dateutil.tz import tzlocal
from domain.entity import Entity, EntityOrigin
from domain.exception.exceptions import (
    EntityNotFound,
    ExecutionConflict,
    ExternalEntityLinkError,
    ProviderInstitutionNotFound,
)
from domain.external_entity import (
    ConnectExternalEntityRequest,
    ExternalEntity,
    ExternalEntityConnectionResult,
    ExternalEntityLoginRequest,
    ExternalEntitySetupResponseCode,
    ExternalEntityStatus,
)
from domain.external_integration import (
    ExternalIntegrationId,
)
from domain.use_cases.connect_external_entity import ConnectExternalEntity


class ConnectExternalEntityImpl(ConnectExternalEntity):
    DEFAULT_PROVIDER = ExternalIntegrationId.GOCARDLESS

    def __init__(
        self,
        entity_port: EntityPort,
        external_entity_port: ExternalEntityPort,
        external_entity_fetchers: dict[ExternalIntegrationId, ExternalEntityFetcher],
        config_port: ConfigPort,
        file_storage_port: FileStoragePort,
    ):
        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._external_entity_fetchers = external_entity_fetchers
        self._config_port = config_port
        self._file_storage_port = file_storage_port

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    async def execute(
        self, request: ConnectExternalEntityRequest
    ) -> ExternalEntityConnectionResult:
        institution_id = request.institution_id

        (
            external_entity,
            institution_details,
            natural_id,
            entity,
            existing_entity_by_name,
        ) = (
            None,
            None,
            None,
            None,
            None,
        )
        migrate_existing_manual_entity = False
        if request.external_entity_id:
            external_entity_id = request.external_entity_id
            external_entity = self._external_entity_port.get_by_id(external_entity_id)
            if not external_entity:
                raise EntityNotFound(external_entity_id)

            entity = self._entity_port.get_by_id(external_entity.entity_id)
            provider_id = external_entity.provider
            provider = self._setup_provider(provider_id)

        else:
            provider = self._setup_provider(self.DEFAULT_PROVIDER)

            institution_details = await provider.get_entity(request.institution_id)
            if not institution_details:
                raise ProviderInstitutionNotFound()

            natural_id = institution_details.bic or institution_details.id
            entity = self._entity_port.get_by_natural_id(natural_id)
            if entity:
                if entity.origin == EntityOrigin.NATIVE:
                    raise ValueError(
                        "Cannot create existing entity as externally provided"
                    )

                external_entity = self._external_entity_port.get_by_entity_id(entity.id)
                if (
                    external_entity
                    and external_entity.status == ExternalEntityStatus.LINKED
                    and entity.origin == EntityOrigin.EXTERNALLY_PROVIDED
                ):
                    return ExternalEntityConnectionResult(
                        ExternalEntitySetupResponseCode.ALREADY_LINKED
                    )
            else:
                existing_entity_by_name = self._entity_port.get_by_name(
                    institution_details.name
                )
                if (
                    existing_entity_by_name
                    and existing_entity_by_name.origin == EntityOrigin.MANUAL
                ):
                    self._log.warning(
                        "Migrating manually created entity to externally provided"
                    )

                    existing_entity_by_name.origin = EntityOrigin.EXTERNALLY_PROVIDED
                    existing_entity_by_name.natural_id = natural_id

                    entity = existing_entity_by_name
                    migrate_existing_manual_entity = True

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            if not entity:
                entity_id = uuid4()
                entity = Entity(
                    id=entity_id,
                    name=institution_details.name,
                    natural_id=natural_id,
                    type=institution_details.type,
                    origin=EntityOrigin.EXTERNALLY_PROVIDED,
                )
                self._entity_port.insert(entity)
                self._save_icon(institution_details.icon, str(entity_id))

            if not external_entity:
                external_entity = ExternalEntity(
                    id=uuid4(),
                    entity_id=entity.id,
                    status=ExternalEntityStatus.UNLINKED,
                    provider=self.DEFAULT_PROVIDER,
                )

            fetch_request = ExternalEntityLoginRequest(
                external_entity=external_entity,
                redirect_host=request.redirect_host,
                institution_id=institution_id,
                relink=request.relink,
                user_language=request.user_language,
            )

            try:
                response = await provider.create_or_link(fetch_request)
            except ExternalEntityLinkError as e:
                if e.orphan_external_entity and external_entity:
                    self._external_entity_port.delete_by_id(external_entity.id)
                raise

            if response.code == ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK:
                try:
                    external_entity.date = datetime.now(tzlocal())
                    external_entity.status = ExternalEntityStatus.UNLINKED
                    external_entity.provider_instance_id = response.provider_instance_id
                    external_entity.payload = response.payload

                    self._external_entity_port.upsert(external_entity)

                    if migrate_existing_manual_entity:
                        self._entity_port.update(existing_entity_by_name)

                    response.id = external_entity.id

                except Exception:
                    if response.provider_instance_id:
                        try:
                            await provider.unlink(response.provider_instance_id)
                        except Exception as e:
                            self._log.error(
                                f"Failed to unlink provider instance {response.provider_instance_id} after error during setup: {e}"
                            )
                    raise

            return response

    def _save_icon(self, icon_url: str, entity_id: str) -> Optional[str]:
        extension = icon_url.split(".")[-1].split("?")[0]
        if extension.lower() not in ["png", "jpg", "jpeg", "svg", "webp"]:
            self._log.warning(
                f"Unsupported file extension '{extension}' for icon URL: {icon_url}"
            )
            return None

        return self._file_storage_port.save_from_url(
            icon_url, "entities/logos", filename=f"{entity_id}.{extension}"
        )

    def _setup_provider(self, external_integration_id: ExternalIntegrationId):
        provider = self._external_entity_fetchers[external_integration_id]
        provider.setup(
            external_entity_provider_integrations_from_config(
                self._config_port.load().integrations
            ),
        )
        return provider
