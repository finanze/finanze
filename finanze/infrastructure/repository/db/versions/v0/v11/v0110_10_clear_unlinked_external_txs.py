from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

UNLINKED_EXTERNAL_ENTITIES = """
    SELECT e.id
    FROM entities e
    WHERE e.origin = 'EXTERNALLY_PROVIDED'
      AND NOT EXISTS (SELECT 1 FROM external_entities ee WHERE ee.entity_id = e.id)
"""

SQL = f"""
      DELETE
      FROM account_transactions
      WHERE source = 'REAL'
        AND entity_id IN ({UNLINKED_EXTERNAL_ENTITIES});

      DELETE
      FROM last_fetches
      WHERE entity_id IN ({UNLINKED_EXTERNAL_ENTITIES});
      """


class V011010ClearUnlinkedExternalTxs(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.11.0:10_clear_unlinked_external_txs"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
