from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE derivative_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          symbol             TEXT        NOT NULL,
          underlying_asset   VARCHAR(32) NOT NULL,
          contract_type      VARCHAR(32) NOT NULL,
          direction          VARCHAR(16) NOT NULL,
          size               TEXT        NOT NULL,
          entry_price        TEXT        NOT NULL,
          currency           VARCHAR(10) NOT NULL,
          mark_price         TEXT,
          market_value       TEXT,
          unrealized_pnl     TEXT,
          leverage           TEXT,
          margin             TEXT,
          margin_type        VARCHAR(16),
          liquidation_price  TEXT,
          isin               VARCHAR(12),
          strike_price       TEXT,
          knock_out_price    TEXT,
          ratio              TEXT,
          issuer             TEXT,
          underlying_symbol  VARCHAR(20),
          underlying_isin    VARCHAR(12),
          expiry             DATE,
          name               TEXT,
          initial_investment TEXT
      );

      CREATE INDEX idx_derp_global_position_id ON derivative_positions (global_position_id);

      INSERT INTO crypto_assets (id, name, symbol, icon_urls, external_ids)
      VALUES ('bfc00000-0000-0000-0000-000000000001', 'Binance Futures Credit', 'BNFCR',
              json_array('/icons/binance-dark.png'), json_object());
      """


class V0811Derivatives(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:11_derivatives"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
