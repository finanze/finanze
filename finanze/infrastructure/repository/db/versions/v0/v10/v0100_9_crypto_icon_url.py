from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = "ALTER TABLE crypto_currency_positions ADD COLUMN icon_url TEXT;"


class V01009CryptoIconUrl(DBVersionMigration):
    @property
    def name(self):
        return "v0.10.0:9_crypto_icon_url"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(SQL)
