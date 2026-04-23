import json

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

IBKR_ENTITY_ID = "e0000000-0000-0000-0000-000000000013"


class V0812IBKRCredentials(DBVersionMigration):
    @property
    def name(self):
        return "v0.8.0:12_ibkr_credentials"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            "SELECT credentials FROM entity_credentials WHERE entity_id = ?",
            (IBKR_ENTITY_ID,),
        )
        row = await cursor.fetchone()
        if row is None:
            return

        credentials = json.loads(row[0]) if row[0] else {}
        if credentials == {}:
            updated = json.dumps({"user": "", "password": ""})
            await cursor.execute(
                "UPDATE entity_credentials SET credentials = ? WHERE entity_id = ?",
                (updated, IBKR_ENTITY_ID),
            )
