from application.ports.external_integration_port import ExternalIntegrationPort
from domain.external_integration import (
    ExternalIntegration,
    ExternalIntegrationId,
    ExternalIntegrationType,
    ExternalIntegrationStatus,
)
from infrastructure.repository.db.client import DBClient


class ExternalIntegrationRepository(ExternalIntegrationPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def update_status(
        self, integration: ExternalIntegrationId, status: ExternalIntegrationStatus
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                UPDATE external_integrations
                SET status = ?
                WHERE id = ?
                """,
                (status.value, integration.value),
            )

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
