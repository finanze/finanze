from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE crypto_wallets
          ADD COLUMN include_wallet_tokens INTEGER NOT NULL DEFAULT 0;
      """


class V01007IncludeWalletTokens(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:7_include_wallet_tokens"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for s in self.parse_block(SQL):
            await cursor.execute(s)
