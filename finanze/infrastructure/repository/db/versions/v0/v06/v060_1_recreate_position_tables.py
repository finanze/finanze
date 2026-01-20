from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      -- We do a little trick in order to achieve the foreign_keys disable in a TX
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = OFF;
      BEGIN TRANSACTION;
      
      -- Recreate account_positions card_positions crowdlending_positions deposit_positions factoring_positions real_estate_cf_positions
      DROP INDEX IF EXISTS idx_ap_global_position_id;
      DROP INDEX IF EXISTS idx_cp_global_position_id;
      DROP INDEX IF EXISTS idx_clp_global_position_id;
      DROP INDEX IF EXISTS idx_dp_global_position_id;
      DROP INDEX IF EXISTS idx_facp_global_position_id;
      DROP INDEX IF EXISTS idx_recfp_global_position_id;

      create table account_positions_new
      (
          id                 CHAR(36) primary key,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          type               VARCHAR(32) not null,
          name               TEXT,
          iban               VARCHAR(32),
          total              TEXT        not null,
          currency           CHAR(3)     not null,
          interest           TEXT,
          retained           TEXT,
          pending_transfers  TEXT
      );

      create table card_positions_new
      (
          id                 CHAR(36) primary key,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          type               VARCHAR(32) not null,
          name               TEXT,
          currency           CHAR(3)     not null,
          ending             TEXT,
          card_limit         TEXT,
          used               TEXT,
          active             BOOLEAN     not null,
          related_account    CHAR(36) references account_positions on update cascade on delete cascade
      );

      create table crowdlending_positions_new
      (
          id                     CHAR(36) primary key,
          global_position_id     CHAR(36)         NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          currency               CHAR(3)          not null,
          distribution           JSON             not null,
          total                  TEXT default '0' not null,
          weighted_interest_rate TEXT default '0' not null
      );

      create table deposit_positions_new
      (
          id                 CHAR(36) primary key,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT     not null,
          amount             TEXT     not null,
          currency           CHAR(3)  not null,
          expected_interests TEXT     not null,
          interest_rate      TEXT     not null,
          creation           DATETIME not null,
          maturity           DATE     not null
      );

      create table factoring_positions_new
      (
          id                  CHAR(36) primary key,
          global_position_id  CHAR(36)         NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name                TEXT             not null,
          amount              TEXT             not null,
          currency            CHAR(3)          not null,
          interest_rate       TEXT             not null,
          gross_interest_rate TEXT             not null,
          last_invest_date    DATETIME         not null,
          maturity            DATE             not null,
          type                VARCHAR(32)      not null,
          state               VARCHAR(32)      not null,
          profitability       TEXT default '0' not null
      );

      create table real_estate_cf_positions_new
      (
          id                 CHAR(36) primary key,
          global_position_id CHAR(36)         NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT             not null,
          amount             TEXT             not null,
          pending_amount     TEXT             not null,
          currency           CHAR(3)          not null,
          interest_rate      TEXT             not null,
          last_invest_date   DATETIME,
          maturity           DATE             not null,
          type               VARCHAR(32)      not null,
          business_type      VARCHAR(32)      not null,
          state              VARCHAR(32)      not null,
          extended_maturity  DATE,
          profitability      TEXT default '0' not null
      );

      INSERT INTO account_positions_new
      SELECT *
      FROM account_positions
      WHERE global_position_id IS NOT NULL AND global_position_id IN (SELECT id FROM global_positions);
      INSERT INTO card_positions_new
      SELECT *
      FROM card_positions
      WHERE global_position_id IS NOT NULL AND global_position_id IN (SELECT id FROM global_positions);
      INSERT INTO crowdlending_positions_new
      SELECT *
      FROM crowdlending_positions
      WHERE global_position_id IS NOT NULL AND global_position_id IN (SELECT id FROM global_positions);
      INSERT INTO deposit_positions_new
      SELECT *
      FROM deposit_positions
      WHERE global_position_id IS NOT NULL AND global_position_id IN (SELECT id FROM global_positions);
      INSERT INTO factoring_positions_new
      SELECT *
      FROM factoring_positions
      WHERE global_position_id IS NOT NULL AND global_position_id IN (SELECT id FROM global_positions);
      INSERT INTO real_estate_cf_positions_new
      SELECT *
      FROM real_estate_cf_positions
      WHERE global_position_id IS NOT NULL AND global_position_id IN (SELECT id FROM global_positions);

      DROP TABLE account_positions;
      DROP TABLE card_positions;
      DROP TABLE crowdlending_positions;
      DROP TABLE deposit_positions;
      DROP TABLE factoring_positions;
      DROP TABLE real_estate_cf_positions;

      ALTER TABLE account_positions_new RENAME TO account_positions;
      ALTER TABLE card_positions_new RENAME TO card_positions;
      ALTER TABLE crowdlending_positions_new RENAME TO crowdlending_positions;
      ALTER TABLE deposit_positions_new RENAME TO deposit_positions;
      ALTER TABLE factoring_positions_new RENAME TO factoring_positions;
      ALTER TABLE real_estate_cf_positions_new RENAME TO real_estate_cf_positions;

      CREATE INDEX idx_ap_global_position_id ON account_positions (global_position_id);
      CREATE INDEX idx_cp_global_position_id ON card_positions (global_position_id);
      CREATE INDEX idx_clp_global_position_id ON crowdlending_positions (global_position_id);
      CREATE INDEX idx_dp_global_position_id ON deposit_positions (global_position_id);
      CREATE INDEX idx_facp_global_position_id ON factoring_positions (global_position_id);
      CREATE INDEX idx_recfp_global_position_id ON real_estate_cf_positions (global_position_id);

      PRAGMA foreign_key_check;
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = ON;
      BEGIN TRANSACTION;
      -- End of trick, let the normal TX continue
      """


class V0601RecreatePositionTables(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.6.0:1_recreate_position_tables"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
