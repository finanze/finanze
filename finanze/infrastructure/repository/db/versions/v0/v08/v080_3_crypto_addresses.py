from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
-- We do a little trick in order to achieve the foreign_keys disable in a TX
COMMIT TRANSACTION;
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Create new crypto_wallets table (renamed from crypto_wallet_connections)
CREATE TABLE crypto_wallets (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    entity_id       CHAR(36)     NOT NULL REFERENCES entities ON UPDATE CASCADE ON DELETE CASCADE,
    name            TEXT         NOT NULL,
    address_source  VARCHAR(20)  NOT NULL,
    created_at      TIMESTAMP    NOT NULL
);

CREATE INDEX idx_cw_entity_id ON crypto_wallets (entity_id);

INSERT INTO crypto_wallets (id, entity_id, name, address_source, created_at)
SELECT id, entity_id, name, 'MANUAL', created_at
FROM crypto_wallet_connections;

-- Create crypto_wallet_addresses table for manual addresses
CREATE TABLE crypto_wallet_addresses (
    wallet_id   CHAR(36)    NOT NULL,
    address     TEXT        NOT NULL,
    FOREIGN KEY (wallet_id) REFERENCES crypto_wallets (id) ON DELETE CASCADE ON UPDATE CASCADE
);

INSERT INTO crypto_wallet_addresses (wallet_id, address)
SELECT id, address
FROM crypto_wallet_connections;

-- Recreate crypto_currency_positions with updated foreign key reference
CREATE TABLE crypto_currency_positions_new (
    id                 CHAR(36)     NOT NULL PRIMARY KEY,
    global_position_id CHAR(36)     NOT NULL REFERENCES global_positions ON UPDATE CASCADE ON DELETE CASCADE,
    wallet_id          CHAR(36)     REFERENCES crypto_wallets ON UPDATE CASCADE ON DELETE SET NULL,
    name               VARCHAR(150) NOT NULL,
    symbol             VARCHAR(30)  NOT NULL,
    amount             TEXT         NOT NULL,
    type               VARCHAR(20)  NOT NULL,
    market_value       TEXT,
    currency           CHAR(3),
    contract_address   TEXT,
    crypto_asset_id    CHAR(36)     REFERENCES crypto_assets ON UPDATE CASCADE ON DELETE SET NULL
);

INSERT INTO crypto_currency_positions_new
SELECT * FROM crypto_currency_positions;

DROP INDEX idx_ccp_global_position_id;
DROP INDEX idx_ccp_wallet_id;
DROP TABLE crypto_currency_positions;
ALTER TABLE crypto_currency_positions_new RENAME TO crypto_currency_positions;

CREATE INDEX idx_ccp_global_position_id ON crypto_currency_positions (global_position_id);
CREATE INDEX idx_ccp_wallet_id ON crypto_currency_positions (wallet_id);

-- Drop old table
DROP INDEX idx_cwc_address;
DROP INDEX idx_cwc_entity_id;
DROP TABLE crypto_wallet_connections;

-- Create HD wallet tables
CREATE TABLE hd_wallet (
    wallet_id   CHAR(36)     NOT NULL PRIMARY KEY,
    xpub        TEXT         NOT NULL,
    script_type VARCHAR(20)  NOT NULL,
    coin        VARCHAR(30)  NOT NULL,
    account     INTEGER      NOT NULL,
    FOREIGN KEY (wallet_id) REFERENCES crypto_wallets (id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE hd_addresses (
    id              CHAR(36)    NOT NULL PRIMARY KEY,
    hd_wallet_id    CHAR(36)    NOT NULL,
    address_index   INTEGER     NOT NULL,
    "change"        INTEGER     NOT NULL,
    derived_path    TEXT        NOT NULL,
    address         TEXT        NOT NULL,
    pubkey          TEXT        NOT NULL,
    FOREIGN KEY (hd_wallet_id) REFERENCES hd_wallet (wallet_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_hd_addresses_wallet ON hd_addresses (hd_wallet_id);

PRAGMA foreign_key_check;
COMMIT TRANSACTION;
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;
-- End of trick, let the normal TX continue
"""


class V0803CryptoAddresses(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:3_crypto_addresses"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
