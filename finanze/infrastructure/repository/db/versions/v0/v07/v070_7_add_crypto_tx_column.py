from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE investment_transactions
          ADD COLUMN asset_contract_address TEXT DEFAULT NULL;
      """


class V0707CryptoTxColumn(DBVersionMigration):
    @property
    def name(self):
        return "v0.7.0:7_add_crypto_tx_column"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        cursor.execute(SQL)
