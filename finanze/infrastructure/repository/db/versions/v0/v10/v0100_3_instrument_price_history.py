from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE instrument_price_history
      (
          id             CHAR(36)     NOT NULL PRIMARY KEY,
          instrument_key VARCHAR(255) NOT NULL,
          date           DATE         NOT NULL,
          price          TEXT         NOT NULL,
          currency       CHAR(3)      NOT NULL,
          source         VARCHAR(64)  NOT NULL,
          created_at     TIMESTAMP    NOT NULL,
          UNIQUE (instrument_key, date)
      );

      CREATE INDEX idx_instrument_price_history_key_date
          ON instrument_price_history (instrument_key, date);

      CREATE TABLE instrument_symbol_map
      (
          id             CHAR(36)     NOT NULL PRIMARY KEY,
          instrument_key VARCHAR(255) NOT NULL UNIQUE,
          symbol         VARCHAR(64)  NOT NULL,
          source         VARCHAR(64)  NOT NULL,
          resolved_at    TIMESTAMP    NOT NULL
      );

      CREATE TABLE instrument_split_cache
      (
          id             CHAR(36)     NOT NULL PRIMARY KEY,
          instrument_key VARCHAR(255) NOT NULL,
          date           DATE         NOT NULL,
          ratio          TEXT         NOT NULL,
          UNIQUE (instrument_key, date)
      );

      CREATE TABLE instrument_split_checked
      (
          id             CHAR(36)     NOT NULL PRIMARY KEY,
          instrument_key VARCHAR(255) NOT NULL UNIQUE,
          checked_at     TIMESTAMP    NOT NULL
      );

      CREATE TABLE instrument_price_gap
      (
          id             CHAR(36)     NOT NULL PRIMARY KEY,
          instrument_key VARCHAR(255) NOT NULL,
          gap_date       DATE         NOT NULL,
          UNIQUE (instrument_key, gap_date)
      );

      CREATE TABLE instrument_no_result
      (
          id             CHAR(36)     NOT NULL PRIMARY KEY,
          instrument_key VARCHAR(255) NOT NULL UNIQUE,
          marked_at      TIMESTAMP    NOT NULL
      );
      """


class V01003InstrumentPriceHistory(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:3_instrument_price_history"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
