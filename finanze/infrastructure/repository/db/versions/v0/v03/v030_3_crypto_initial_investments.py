from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      PRAGMA foreign_keys=OFF;

      -- Step 1: Migrate crypto_currency_token_positions WITHOUT FK constraint
      DROP INDEX IF EXISTS idx_cctp_wallet_id;
      ALTER TABLE crypto_currency_token_positions RENAME TO crypto_currency_token_positions_old;

      CREATE TABLE crypto_currency_token_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          wallet_id          CHAR(36)     NOT NULL,
          token_id           VARCHAR(255) NOT NULL,
          name               TEXT         NOT NULL,
          symbol             VARCHAR(10)  NOT NULL,
          token              TEXT         NOT NULL,
          amount             TEXT         NOT NULL,
          market_value       TEXT         NOT NULL,
          currency           CHAR(3)      NOT NULL,
          type               VARCHAR(32)
      );

      INSERT INTO crypto_currency_token_positions (id, wallet_id, token_id, name, symbol, token, amount, market_value, currency, type)
          SELECT id, wallet_id, token_id, name, symbol, token, amount, market_value, currency, type
          FROM crypto_currency_token_positions_old;

      DROP TABLE crypto_currency_token_positions_old;

      -- Step 2: Migrate crypto_currency_wallet_positions
      DROP INDEX IF EXISTS idx_ccwp_global_position_id;
      ALTER TABLE crypto_currency_wallet_positions RENAME TO crypto_currency_wallet_positions_old;

      CREATE TABLE crypto_currency_wallet_positions
      (
          id                   CHAR(36) PRIMARY KEY,
          global_position_id   CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          wallet_connection_id CHAR(36)    NOT NULL REFERENCES crypto_wallet_connections (id) ON DELETE CASCADE ON UPDATE CASCADE,
          symbol               VARCHAR(10) NOT NULL,
          amount               TEXT        NOT NULL,
          market_value         TEXT        NOT NULL,
          currency             CHAR(3)     NOT NULL,
          crypto               VARCHAR(32) NOT NULL
      );

      INSERT INTO crypto_currency_wallet_positions (id, global_position_id, wallet_connection_id, symbol, amount, market_value, currency, crypto)
          SELECT id, global_position_id, wallet_connection_id, symbol, amount, market_value, currency, crypto
          FROM crypto_currency_wallet_positions_old;

      DROP TABLE crypto_currency_wallet_positions_old;

      CREATE INDEX idx_ccwp_global_position_id ON crypto_currency_wallet_positions (global_position_id);

      -- Step 3: Recreate crypto_currency_token_positions WITH FK constraint
      ALTER TABLE crypto_currency_token_positions RENAME TO crypto_currency_token_positions_tmp;

      CREATE TABLE crypto_currency_token_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          wallet_id          CHAR(36)     NOT NULL REFERENCES crypto_currency_wallet_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          token_id           VARCHAR(255) NOT NULL,
          name               TEXT         NOT NULL,
          symbol             VARCHAR(10)  NOT NULL,
          token              TEXT         NOT NULL,
          amount             TEXT         NOT NULL,
          market_value       TEXT         NOT NULL,
          currency           CHAR(3)      NOT NULL,
          type               VARCHAR(32)
      );

      INSERT INTO crypto_currency_token_positions (id, wallet_id, token_id, name, symbol, token, amount, market_value, currency, type)
          SELECT id, wallet_id, token_id, name, symbol, token, amount, market_value, currency, type
          FROM crypto_currency_token_positions_tmp;

      DROP TABLE crypto_currency_token_positions_tmp;

      CREATE INDEX idx_cctp_wallet_id ON crypto_currency_token_positions (wallet_id);

      -- Step 4: Create new table for initial investments
      CREATE TABLE crypto_initial_investments
      (
          id                   CHAR(36)    PRIMARY KEY,
          wallet_connection_id CHAR(36)    NOT NULL REFERENCES crypto_wallet_connections (id) ON DELETE CASCADE ON UPDATE CASCADE,
          symbol               VARCHAR(10) NOT NULL,
          type                 VARCHAR(24) NOT NULL,
          currency             CHAR(3)     NOT NULL,
          initial_investment   TEXT        NOT NULL,
          average_buy_price    TEXT        NOT NULL
      );

      CREATE INDEX idx_cii_wallet_conn ON crypto_initial_investments (wallet_connection_id);
      CREATE INDEX idx_cii_wallet_conn_type_symbol ON crypto_initial_investments (wallet_connection_id, type, symbol);

      PRAGMA foreign_keys=ON;
      """


class V0303CryptoInitialInvestments(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.3.0:3_crypto_initial_investments"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
