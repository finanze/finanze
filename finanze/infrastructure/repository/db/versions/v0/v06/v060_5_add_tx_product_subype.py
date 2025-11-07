from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE investment_transactions
          ADD COLUMN product_subtype VARCHAR(32);
      """


class V0605TxProductSubtype(DBVersionMigration):
    @property
    def name(self):
        return "v0.6.0:5_add_tx_product_subtype"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        cursor.execute(SQL)
