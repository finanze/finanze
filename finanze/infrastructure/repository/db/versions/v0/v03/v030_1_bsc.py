from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

ADD_CRYPTO_ENTITIES = """
                      INSERT INTO entities (id, name, type, is_real)
                      VALUES ('c0000000-0000-0000-0000-000000000005', 'Binance Smart Chain', 'CRYPTO_WALLET', TRUE);
                      """


class V0301BSC(DBVersionMigration):
    @property
    def name(self):
        return "v0.3.0:1_bsc"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        cursor.execute(ADD_CRYPTO_ENTITIES)
