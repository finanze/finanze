from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE account_transactions ADD net_amount TEXT;
      """


class V0403(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:3_add_account_tx_net_amount"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
