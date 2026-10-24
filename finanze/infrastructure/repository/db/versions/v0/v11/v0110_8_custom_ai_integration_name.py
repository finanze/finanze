from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration


class V01108CustomAIIntegrationName(DBVersionMigration):
    @property
    def name(self):
        return "v0.11.0:8_custom_ai_integration_name"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            """
            UPDATE external_integrations
            SET name = 'Custom AI'
            WHERE id = 'OPENAI_COMPATIBLE' AND name = 'Custom endpoint'
            """
        )
