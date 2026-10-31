from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration


class V01107McpToolCategories(DBVersionMigration):
    @property
    def name(self):
        return "v0.11.0:7_mcp_tool_categories"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            "ALTER TABLE mcp_config ADD COLUMN category_access TEXT NOT NULL DEFAULT '{}'"
        )
