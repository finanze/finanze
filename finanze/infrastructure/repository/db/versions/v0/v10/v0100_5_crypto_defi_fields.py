from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE crypto_currency_positions ADD COLUMN chain TEXT;
      ALTER TABLE crypto_currency_positions ADD COLUMN protocol TEXT;
      ALTER TABLE crypto_currency_positions ADD COLUMN position_type VARCHAR(20) NOT NULL DEFAULT 'HOLDING';
      """


class V01005CryptoDefiFields(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:5_crypto_defi_fields"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
