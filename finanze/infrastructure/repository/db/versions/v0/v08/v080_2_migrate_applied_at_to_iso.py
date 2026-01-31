from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration
from datetime import datetime


class V0802MigrateAppliedAtToIso(DBVersionMigration):
    @property
    def name(self):
        return "v0.8.0:2_migrate_applied_at_to_iso"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute("SELECT version, applied_at FROM migrations")
        rows = await cursor.fetchall()
        from dateutil.tz import tzlocal

        for version, applied_at in rows:
            if applied_at and not self._is_isoformat(applied_at):
                try:
                    dt = datetime.fromisoformat(applied_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=tzlocal())
                    iso_value = dt.isoformat()
                except (ValueError, TypeError):
                    try:
                        dt = datetime.strptime(applied_at, "%Y-%m-%d %H:%M:%S")
                        dt = dt.replace(tzinfo=tzlocal())
                        iso_value = dt.isoformat()
                    except (ValueError, TypeError):
                        dt = datetime.strptime(applied_at, "%Y-%m-%d %H:%M:%S.%f")
                        dt = dt.replace(tzinfo=tzlocal())
                        iso_value = dt.isoformat()

                await cursor.execute(
                    "UPDATE migrations SET applied_at = ? WHERE version = ?",
                    (iso_value, version),
                )

    @staticmethod
    def _is_isoformat(date_string: str) -> bool:
        return "T" in date_string and (
            "+" in date_string
            or date_string.endswith("Z")
            or date_string.count(":") >= 2
        )
