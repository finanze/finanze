from dataclasses import asdict
from datetime import datetime

from dateutil.tz import tzlocal

from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from domain.available_sources import AvailableSources, AvailableFinancialEntity, FinancialEntityStatus
from domain.native_entities import NATIVE_ENTITIES
from domain.use_cases.get_available_entities import GetAvailableEntities


class GetAvailableEntitiesImpl(GetAvailableEntities):

    def __init__(self,
                 config_port: ConfigPort,
                 credentials_port: CredentialsPort):
        self._config_port = config_port
        self._credentials_port = credentials_port

    async def execute(self) -> AvailableSources:
        scrape_config = self._config_port.load().scrape

        virtual_enabled = scrape_config.virtual.enabled

        logged_entities = self._credentials_port.get_available_entities()
        logged_entity_ids = {e.entity_id: e.expiration for e in logged_entities}

        entities = []
        for native_entity in NATIVE_ENTITIES:
            status = FinancialEntityStatus.DISCONNECTED

            if native_entity.id in logged_entity_ids:
                status = FinancialEntityStatus.CONNECTED

                expiration = logged_entity_ids.get(native_entity.id)
                if expiration and expiration < datetime.now(tzlocal()):
                    status = FinancialEntityStatus.REQUIRES_LOGIN

            entities.append(
                AvailableFinancialEntity(**asdict(native_entity), status=status)
            )

        return AvailableSources(
            virtual=virtual_enabled,
            entities=entities
        )
