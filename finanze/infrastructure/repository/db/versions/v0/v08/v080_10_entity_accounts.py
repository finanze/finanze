from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = OFF;
      BEGIN TRANSACTION;

      -- 1. Create entity_accounts table
      CREATE TABLE entity_accounts (
          id         CHAR(36) NOT NULL PRIMARY KEY,
          name       VARCHAR(100),
          entity_id  CHAR(36) NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
          created_at TIMESTAMP NOT NULL,
          deleted_at TIMESTAMP
      );

      CREATE INDEX idx_ea_entity_id ON entity_accounts (entity_id);

      -- 2. Create entity_accounts from existing credentials (reuse entity_id as account id)
      INSERT INTO entity_accounts (id, name, entity_id, created_at)
      SELECT entity_id, NULL, entity_id, created_at
      FROM entity_credentials;

      -- 3. Recreate entity_credentials with entity_account_id as PK
      CREATE TABLE entity_credentials_new (
          entity_account_id CHAR(36) NOT NULL PRIMARY KEY
              REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
          entity_id    CHAR(36) NOT NULL
              REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
          credentials  JSON NOT NULL,
          created_at   TIMESTAMP NOT NULL,
          last_used_at TIMESTAMP DEFAULT NULL,
          expiration   TIMESTAMP DEFAULT NULL
      );

      INSERT INTO entity_credentials_new (entity_account_id, entity_id, credentials, created_at, last_used_at, expiration)
      SELECT entity_id, entity_id, credentials, created_at, last_used_at, expiration
      FROM entity_credentials;

      DROP TABLE entity_credentials;

      ALTER TABLE entity_credentials_new RENAME TO entity_credentials;

      -- 4. Recreate entity_sessions with entity_account_id as PK
      CREATE TABLE entity_sessions_new (
          entity_account_id CHAR(36) NOT NULL PRIMARY KEY
              REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
          entity_id    CHAR(36) NOT NULL
              REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
          created_at   TIMESTAMP NOT NULL,
          expiration   TIMESTAMP,
          payload      JSON NOT NULL
      );

      INSERT INTO entity_sessions_new (entity_account_id, entity_id, created_at, expiration, payload)
      SELECT entity_id, entity_id, created_at, expiration, payload
      FROM entity_sessions;

      DROP TABLE entity_sessions;

      ALTER TABLE entity_sessions_new RENAME TO entity_sessions;

      -- 5. Add entity_account_id to data tables
      ALTER TABLE global_positions ADD COLUMN entity_account_id CHAR(36)
          REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE;

      ALTER TABLE investment_transactions ADD COLUMN entity_account_id CHAR(36)
          REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE;

      ALTER TABLE account_transactions ADD COLUMN entity_account_id CHAR(36)
          REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE;

      ALTER TABLE investment_historic ADD COLUMN entity_account_id CHAR(36)
          REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE;

      ALTER TABLE periodic_contributions ADD COLUMN entity_account_id CHAR(36)
          REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE;

      -- 6. Backfill entity_account_id for existing data where an account exists
      UPDATE global_positions SET entity_account_id = entity_id
      WHERE entity_id IN (SELECT id FROM entity_accounts);

      UPDATE investment_transactions SET entity_account_id = entity_id
      WHERE entity_id IN (SELECT id FROM entity_accounts);

      UPDATE account_transactions SET entity_account_id = entity_id
      WHERE entity_id IN (SELECT id FROM entity_accounts);

      UPDATE investment_historic SET entity_account_id = entity_id
      WHERE entity_id IN (SELECT id FROM entity_accounts);

      UPDATE periodic_contributions SET entity_account_id = entity_id
      WHERE entity_id IN (SELECT id FROM entity_accounts);

      -- 7. Recreate last_fetches with entity_account_id
      DROP INDEX IF EXISTS idx_lfetches_entity_id;

      CREATE TABLE last_fetches_new (
          id                 CHAR(36) NOT NULL PRIMARY KEY,
          entity_id          CHAR(36) NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
          feature            VARCHAR(255) NOT NULL,
          date               TIMESTAMP NOT NULL,
          entity_account_id  CHAR(36) REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE
      );

      INSERT INTO last_fetches_new (id, entity_id, feature, date, entity_account_id)
      SELECT lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab', abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))),
             entity_id, feature, date,
             CASE WHEN entity_id IN (SELECT id FROM entity_accounts) THEN entity_id ELSE NULL END
      FROM last_fetches;

      DROP TABLE last_fetches;

      ALTER TABLE last_fetches_new RENAME TO last_fetches;

      CREATE INDEX idx_lfetches_entity_id ON last_fetches (entity_id);
      CREATE UNIQUE INDEX idx_lfetches_unique ON last_fetches (entity_id, feature, COALESCE(entity_account_id, ''));

      PRAGMA foreign_key_check;
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = ON;
      BEGIN TRANSACTION;
      -- End of trick, let the normal TX continue
      """


class V0810EntityAccounts(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:10_entity_accounts"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
