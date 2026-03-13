from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      CREATE TABLE public_keychain
      (
          key        VARCHAR(64) PRIMARY KEY,
          value      VARCHAR(256) NOT NULL,
          algo       INTEGER NOT NULL,
          version    INTEGER NOT NULL,
          updated_at TIMESTAMP NOT NULL
      );

      INSERT INTO public_keychain (key, value, algo, version, updated_at)
      VALUES ('f18b4d3e78064ef6', 'b1kjCh0wCwQdLi4uLi4iHhggGxsrBxskJTUjFTY4Kxs5BTBZGyMaNgpvWg', 1, 1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'));

      INSERT INTO public_keychain (key, value, algo, version, updated_at)
      VALUES ('6a2fcf4c79f7e985', '88DBwsbEwMqVxMKQxsfKlsWSkcTEwMXLkJXCkcfDlpDL8w', 1, 1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'));

      INSERT INTO public_keychain (key, value, algo, version, updated_at)
      VALUES ('f294b5d5eca3b1dc', 'LxZieEh6YR5cY2FKHkUdTmgvrUnxetCymA', 1, 1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'));
      """


class V0807PublicKeychain(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:7_public_keychain"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
