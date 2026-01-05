import json
from typing import Optional

from application.ports.external_integration_port import ExternalIntegrationPort
from domain.external_integration import (
    ExternalIntegration,
    ExternalIntegrationId,
    ExternalIntegrationPayload,
    ExternalIntegrationStatus,
    ExternalIntegrationType,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.external_integration.queries import (
    ExternalIntegrationQueries,
)


class ExternalIntegrationRepository(ExternalIntegrationPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def deactivate(self, integration: ExternalIntegrationId):
        with self._db_client.tx() as cursor:
            cursor.execute(
                ExternalIntegrationQueries.DEACTIVATE,
                (ExternalIntegrationStatus.OFF.value, integration.value),
            )

    def activate(
        self, integration: ExternalIntegrationId, payload: ExternalIntegrationPayload
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                ExternalIntegrationQueries.ACTIVATE,
                (
                    ExternalIntegrationStatus.ON.value,
                    json.dumps(payload),
                    integration.value,
                ),
            )

    def get_payload(
        self, integration: ExternalIntegrationId
    ) -> Optional[ExternalIntegrationPayload]:
        with self._db_client.read() as cursor:
            cursor.execute(
                ExternalIntegrationQueries.GET_PAYLOAD,
                (integration.value, ExternalIntegrationStatus.ON.value),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            return (
                ExternalIntegrationPayload(**json.loads(row["payload"]))
                if row["payload"]
                else None
            )

    def get_payloads_by_type(
        self, integration_type: ExternalIntegrationType
    ) -> dict[ExternalIntegrationId, ExternalIntegrationPayload]:
        with self._db_client.read() as cursor:
            cursor.execute(
                ExternalIntegrationQueries.GET_PAYLOADS_BY_TYPE,
                (integration_type.value, ExternalIntegrationStatus.ON.value),
            )

            rows = cursor.fetchall()
            return {
                ExternalIntegrationId(row["id"]): ExternalIntegrationPayload(
                    **json.loads(row["payload"])
                )
                for row in rows
                if row["payload"]
            }

    def get_all(self) -> list[ExternalIntegration]:
        with self._db_client.read() as cursor:
            cursor.execute(ExternalIntegrationQueries.GET_ALL)
            rows = cursor.fetchall()
            return [
                ExternalIntegration(
                    id=ExternalIntegrationId(row["id"]),
                    name=row["name"],
                    type=ExternalIntegrationType(row["type"]),
                    status=ExternalIntegrationStatus(row["status"]),
                )
                for row in rows
            ]
