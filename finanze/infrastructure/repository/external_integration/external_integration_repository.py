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


class ExternalIntegrationRepository(ExternalIntegrationPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def deactivate(self, integration: ExternalIntegrationId):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE external_integrations
                SET status  = ?,
                    payload = NULL
                WHERE id = ?
                """,
                (ExternalIntegrationStatus.OFF.value, integration.value),
            )

    def activate(
        self, integration: ExternalIntegrationId, payload: ExternalIntegrationPayload
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE external_integrations
                SET status  = ?,
                    payload = ?
                WHERE id = ?
                """,
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
                "SELECT payload FROM external_integrations WHERE id = ? AND status = ? AND payload IS NOT NULL",
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
                """
                SELECT id, payload
                FROM external_integrations
                WHERE type = ?
                  AND status = ?
                  AND payload IS NOT NULL
                """,
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
            cursor.execute(
                """
                SELECT id, name, type, status
                FROM external_integrations
                """
            )
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
