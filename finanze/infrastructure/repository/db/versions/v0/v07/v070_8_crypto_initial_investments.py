from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      CREATE TABLE crypto_currency_initial_investments
      (
          id                       CHAR(36) PRIMARY KEY,
          crypto_currency_position CHAR(36) NOT NULL REFERENCES crypto_currency_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          currency                 CHAR(3)  NOT NULL,
          initial_investment       TEXT     NOT NULL,
          average_buy_price        TEXT     NOT NULL
      );

      CREATE INDEX idx_ccii_position ON crypto_currency_initial_investments (crypto_currency_position);
      """


class V0708CryptoInitialInvestments(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.7.0:8_crypto_initial_investments"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
