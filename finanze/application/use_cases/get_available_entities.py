from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from application.ports.entity_port import EntityPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.available_sources import (
    AvailableFinancialEntity,
    AvailableSources,
    FinancialEntityStatus,
)
from domain.entity import EntityType, Feature
from domain.native_entities import NATIVE_ENTITIES
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.virtual_fetch import VirtualDataImport


def get_last_fetches_for_virtual(
    virtual_imports: list[VirtualDataImport],
) -> dict[Feature, datetime]:
    last_fetch = {}
    for virtual_import in virtual_imports:
        last_fetch[virtual_import.feature] = virtual_import.date

    return last_fetch


class GetAvailableEntitiesImpl(GetAvailableEntities):
    def __init__(
        self,
        config_port: ConfigPort,
        entity_port: EntityPort,
        credentials_port: CredentialsPort,
        crypto_wallet_connections_port: CryptoWalletConnectionPort,
        last_fetches_port: LastFetchesPort,
        virtual_import_registry: VirtualImportRegistry,
    ):
        self._config_port = config_port
        self._entity_port = entity_port
        self._credentials_port = credentials_port
        self._crypto_wallet_connections_port = crypto_wallet_connections_port
        self._last_fetches_port = last_fetches_port
        self._virtual_import_registry = virtual_import_registry

    async def execute(self) -> AvailableSources:
        fetch_config = self._config_port.load().fetch

        virtual_enabled = fetch_config.virtual.enabled

        logged_entities = self._credentials_port.get_available_entities()
        logged_entity_ids = {e.entity_id: e.expiration for e in logged_entities}

        all_entities = self._entity_port.get_all()

        native_entities_by_id = {e.id: e for e in NATIVE_ENTITIES}

        last_virtual_imported_entities = self.get_last_virtual_imports_by_entity()

        entities = []
        for entity in all_entities:
            native_entity = native_entities_by_id.get(entity.id)
            status = None
            wallets = None
            if entity.type == EntityType.FINANCIAL_INSTITUTION:
                status = FinancialEntityStatus.DISCONNECTED

                if entity.is_real:
                    if entity.id in logged_entity_ids:
                        status = FinancialEntityStatus.CONNECTED

                        expiration = logged_entity_ids.get(entity.id)
                        if expiration and expiration < datetime.now(tzlocal()):
                            status = FinancialEntityStatus.REQUIRES_LOGIN
                else:
                    if entity.id in last_virtual_imported_entities:
                        status = FinancialEntityStatus.CONNECTED

            else:
                wallets = self._crypto_wallet_connections_port.get_by_entity_id(
                    entity.id
                )

            dict_entity = asdict(native_entity or entity)

            last_fetch = {}
            if entity.is_real:
                last_fetch_records = self._last_fetches_port.get_by_entity_id(entity.id)
                last_fetch = {r.feature: r.date for r in last_fetch_records}
            else:
                dict_entity["features"] = []

            entity_virtual_imports = last_virtual_imported_entities.get(entity.id)
            if entity_virtual_imports:
                virtual_last_fetch = get_last_fetches_for_virtual(
                    entity_virtual_imports
                )
                if entity.is_real:
                    last_fetch = {**virtual_last_fetch, **last_fetch}
                else:
                    last_fetch = virtual_last_fetch
                    dict_entity["features"] = list(virtual_last_fetch.keys())

            entities.append(
                AvailableFinancialEntity(
                    **dict_entity,
                    status=status,
                    connected=wallets,
                    last_fetch=last_fetch,
                )
            )

        return AvailableSources(virtual=virtual_enabled, entities=entities)

    def get_last_virtual_imports_by_entity(self) -> dict[UUID, list[VirtualDataImport]]:
        last_virtual_imports = self._virtual_import_registry.get_last_import_records()
        last_virtual_imported_entities = {}
        for virtual_import in last_virtual_imports:
            if virtual_import.entity_id not in last_virtual_imported_entities:
                last_virtual_imported_entities[virtual_import.entity_id] = []

            last_virtual_imported_entities[virtual_import.entity_id].append(
                virtual_import
            )

        return last_virtual_imported_entities
