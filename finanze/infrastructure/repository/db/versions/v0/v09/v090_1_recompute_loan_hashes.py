from domain.data_init import DatasourceInitContext
from domain.global_position import compute_loan_hash
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration


class V0901RecomputeLoanHashes(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:1_recompute_loan_hashes"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            "SELECT lp.id, lp.hash, gp.entity_id, lp.loan_amount, lp.creation "
            "FROM loan_positions lp "
            "JOIN global_positions gp ON lp.global_position_id = gp.id"
        )
        rows = list(cursor)

        hash_remap: dict[str, str] = {}
        for row in rows:
            new_hash = compute_loan_hash(
                str(row["entity_id"]),
                str(row["loan_amount"]),
                str(row["creation"]),
            )
            old_hash = row["hash"]
            if old_hash and old_hash != new_hash:
                hash_remap[old_hash] = new_hash
            await cursor.execute(
                "UPDATE loan_positions SET hash = ? WHERE id = ?",
                (new_hash, row["id"]),
            )

        for old_hash, new_hash in hash_remap.items():
            await cursor.execute(
                "UPDATE real_estate_flows SET extra_reference = ? "
                "WHERE extra_reference = ?",
                (new_hash, old_hash),
            )
