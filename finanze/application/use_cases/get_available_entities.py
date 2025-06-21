from dataclasses import asdict
from datetime import datetime

from application.ports.config_port import ConfigPort
from application.ports.credentials_port import CredentialsPort
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from dateutil.tz import tzlocal
from domain.available_sources import (
    AvailableFinancialEntity,
    AvailableSources,
    FinancialEntityStatus,
)
from domain.entity import EntityType
from domain.native_entities import NATIVE_ENTITIES
from domain.use_cases.get_available_entities import GetAvailableEntities


class GetAvailableEntitiesImpl(GetAvailableEntities):
    def __init__(
        self,
        config_port: ConfigPort,
        credentials_port: CredentialsPort,
        crypto_wallet_connections_port: CryptoWalletConnectionPort,
    ):
        self._config_port = config_port
        self._credentials_port = credentials_port
        self._crypto_wallet_connections_port = crypto_wallet_connections_port

    async def execute(self) -> AvailableSources:
        fetch_config = self._config_port.load().fetch

        virtual_enabled = fetch_config.virtual.enabled

        logged_entities = self._credentials_port.get_available_entities()
        logged_entity_ids = {e.entity_id: e.expiration for e in logged_entities}

        entities = []
        for native_entity in NATIVE_ENTITIES:
            status = None
            wallets = None
            if native_entity.type == EntityType.FINANCIAL_INSTITUTION:
                status = FinancialEntityStatus.DISCONNECTED

                if native_entity.id in logged_entity_ids:
                    status = FinancialEntityStatus.CONNECTED

                    expiration = logged_entity_ids.get(native_entity.id)
                    if expiration and expiration < datetime.now(tzlocal()):
                        status = FinancialEntityStatus.REQUIRES_LOGIN
            else:
                wallets = self._crypto_wallet_connections_port.get_by_entity_id(
                    native_entity.id
                )

            entities.append(
                AvailableFinancialEntity(
                    **asdict(native_entity), status=status, connected=wallets
                )
            )

        return AvailableSources(virtual=virtual_enabled, entities=entities)
