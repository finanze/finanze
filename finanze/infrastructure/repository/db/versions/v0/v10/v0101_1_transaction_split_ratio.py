from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration


class V01011TransactionSplitRatio(DBVersionMigration):
    @property
    def name(self):
        return "v0.10.1:1_transaction_split_ratio"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            "ALTER TABLE investment_transactions ADD COLUMN split_ratio TEXT"
        )
