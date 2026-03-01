from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
COMMIT TRANSACTION;
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE hd_wallet_new (
    wallet_id   CHAR(36)     NOT NULL PRIMARY KEY,
    xpub        TEXT         NOT NULL,
    script_type VARCHAR(20)  NOT NULL,
    coin        VARCHAR(30)  NOT NULL,
    FOREIGN KEY (wallet_id) REFERENCES crypto_wallets (id) ON DELETE CASCADE ON UPDATE CASCADE
);

INSERT INTO hd_wallet_new (wallet_id, xpub, script_type, coin)
SELECT wallet_id, xpub, script_type, coin
FROM hd_wallet;

DROP TABLE hd_wallet;
ALTER TABLE hd_wallet_new RENAME TO hd_wallet;

PRAGMA foreign_key_check;
COMMIT TRANSACTION;
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;
"""


class V0804RemoveHdWalletAccount(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:4_remove_hd_wallet_account"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
