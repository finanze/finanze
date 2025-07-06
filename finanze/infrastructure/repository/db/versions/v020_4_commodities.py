from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration


DDL = """
      -- COMMODITY POSITIONS
      CREATE TABLE commodity_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT        NOT NULL,
          type               VARCHAR(32) NOT NULL,
          amount             TEXT        NOT NULL,
          unit               VARCHAR(32) NOT NULL,
          market_value       TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          initial_investment TEXT,
          average_buy_price  TEXT
      );

      CREATE INDEX idx_comp_global_position_id ON commodity_positions (global_position_id);
      """

ADD_CRYPTO_ENTITIES = """
                      INSERT INTO entities (id, name, type, is_real)
                      VALUES ('ccccdddd-0000-0000-0000-000000000000', 'Commodity Source', 'COMMODITY', TRUE)
                      """


class V0204Commodities(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.2.0:4_commodities"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)

        cursor.execute(ADD_CRYPTO_ENTITIES)
