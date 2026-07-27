from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('ce000000-0000-0000-0000-000000000002', 'Polymarket', NULL, 'MARKET_FORECAST_PLATFORM', 'NATIVE');

      CREATE TABLE market_forecast_positions
      (
          id                      CHAR(36) PRIMARY KEY,
          global_position_id      CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          symbol                  TEXT        NOT NULL,
          market_type             VARCHAR(32),
          direction               VARCHAR(16) NOT NULL,
          size                    TEXT        NOT NULL,
          entry_price             TEXT        NOT NULL,
          currency                VARCHAR(10) NOT NULL,
          mark_price              TEXT,
          market_value            TEXT,
          unrealized_pnl          TEXT,
          underlying_symbol       VARCHAR(255),
          expiry                  DATE,
          name                    TEXT,
          initial_investment      TEXT,
          market_slug             TEXT,
          event_slug              TEXT,
          outcome                 TEXT,
          condition_id            TEXT,
          token_id                TEXT
      );

      CREATE INDEX idx_mfp_global_position_id ON market_forecast_positions (global_position_id);
      """


class V01001Polymarket(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:1_polymarket"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
