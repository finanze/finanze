from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE crypto_currency_positions ADD COLUMN chain TEXT;
      ALTER TABLE crypto_currency_positions ADD COLUMN protocol TEXT;
      ALTER TABLE crypto_currency_positions ADD COLUMN position_type VARCHAR(20) NOT NULL DEFAULT 'HOLDING';
      ALTER TABLE crypto_currency_positions ADD COLUMN icon_url TEXT;
      ALTER TABLE crypto_wallets ADD COLUMN include_wallet_tokens INTEGER NOT NULL DEFAULT 0;
      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('ZERION', 'Zerion', 'CRYPTO_PROVIDER', 'OFF');
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('c0000000-0000-0000-0000-000000000006', 'Zerion', NULL, 'CRYPTO_WALLET', 'NATIVE');
      """


class V01005CryptoDefiZerion(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:5_crypto_defi_zerion"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
