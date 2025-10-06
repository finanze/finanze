from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from application.ports.entity_port import EntityPort
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.available_sources import (
    AvailableSource,
    AvailableSources,
    FinancialEntityStatus,
)
from domain.entity import EntityOrigin, EntityType, Feature
from domain.external_entity import EXTERNAL_ENTITY_FEATURES, ExternalEntityStatus
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
    LISTED_ENTITY_TYPES = [EntityType.FINANCIAL_INSTITUTION, EntityType.CRYPTO_WALLET]

    def __init__(
        self,
        entity_port: EntityPort,
        external_entity_port: ExternalEntityPort,
        credentials_port: CredentialsPort,
        crypto_wallet_connections_port: CryptoWalletConnectionPort,
        last_fetches_port: LastFetchesPort,
        virtual_import_registry: VirtualImportRegistry,
    ):
        self._entity_port = entity_port
        self._external_entity_port = external_entity_port
        self._credentials_port = credentials_port
        self._crypto_wallet_connections_port = crypto_wallet_connections_port
        self._last_fetches_port = last_fetches_port
        self._virtual_import_registry = virtual_import_registry

    def execute(self) -> AvailableSources:
        logged_entities = self._credentials_port.get_available_entities()
        logged_entity_ids = {e.entity_id: e.expiration for e in logged_entities}

        all_entities = self._entity_port.get_all()

        native_entities_by_id = {e.id: e for e in NATIVE_ENTITIES}

        last_virtual_imported_entities = self.get_last_virtual_imports_by_entity()

        entities = []
        for entity in all_entities:
            if entity.type not in self.LISTED_ENTITY_TYPES:
                continue
            native_entity = native_entities_by_id.get(entity.id)
            status = None
            wallets = None
            external_entity_id = None

            last_virtual_imported_data = last_virtual_imported_entities.get(entity.id)
            virtual_features = {}
            if last_virtual_imported_data:
                virtual_features = {
                    vi.feature: vi.date for vi in last_virtual_imported_data
                }

            dict_entity = asdict(native_entity or entity)

            if entity.origin == EntityOrigin.EXTERNALLY_PROVIDED:
                external_entity = self._external_entity_port.get_by_entity_id(entity.id)
                if not external_entity:
                    status = FinancialEntityStatus.DISCONNECTED
                    dict_entity["features"] = []
                else:
                    status = (
                        FinancialEntityStatus.CONNECTED
                        if external_entity.status == ExternalEntityStatus.LINKED
                        else FinancialEntityStatus.REQUIRES_LOGIN
                    )
                    external_entity_id = external_entity.id
                    dict_entity["features"] = EXTERNAL_ENTITY_FEATURES

            elif entity.type == EntityType.FINANCIAL_INSTITUTION:
                status = FinancialEntityStatus.DISCONNECTED

                if entity.origin != EntityOrigin.MANUAL:
                    if entity.id in logged_entity_ids:
                        status = FinancialEntityStatus.CONNECTED

                        expiration = logged_entity_ids.get(entity.id)
                        if expiration and expiration < datetime.now(tzlocal()):
                            status = FinancialEntityStatus.REQUIRES_LOGIN
                else:
                    if virtual_features:
                        status = FinancialEntityStatus.CONNECTED

            else:
                wallets = self._crypto_wallet_connections_port.get_by_entity_id(
                    entity.id
                )

            last_fetch = {}
            if entity.origin != EntityOrigin.MANUAL:
                if status != FinancialEntityStatus.DISCONNECTED:
                    last_fetch_records = self._last_fetches_port.get_by_entity_id(
                        entity.id
                    )
                    last_fetch = {r.feature: r.date for r in last_fetch_records}
            else:
                dict_entity["features"] = []

            entity_virtual_imports = last_virtual_imported_entities.get(entity.id)
            if entity_virtual_imports:
                virtual_last_fetch = get_last_fetches_for_virtual(
                    entity_virtual_imports
                )
                if entity.origin == EntityOrigin.MANUAL:
                    last_fetch = virtual_last_fetch
                    dict_entity["features"] = list(virtual_last_fetch.keys())

            entities.append(
                AvailableSource(
                    **dict_entity,
                    status=status,
                    connected=wallets,
                    last_fetch=last_fetch,
                    external_entity_id=external_entity_id,
                    virtual_features=virtual_features,
                )
            )

        return AvailableSources(entities=entities)

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
