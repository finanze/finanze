import json

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration


def _upgrade_group(group: dict) -> dict:
    text = group.get("text")
    if isinstance(text, dict) and "values" not in text:
        value = text.pop("value", None)
        text["values"] = [value] if value else []
    return group


def upgrade_conditions(raw: str) -> str:
    data = json.loads(raw) if raw else {}
    groups = data if isinstance(data, list) else [data]
    return json.dumps([_upgrade_group(group) for group in groups])


class V01203LabelingRuleMultiConditions(DBVersionMigration):
    @property
    def name(self):
        return "v0.12.0:3_labeling_rule_multi_conditions"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute("SELECT id, conditions FROM labeling_rules")
        rows = await cursor.fetchall()
        for row in rows:
            upgraded = upgrade_conditions(row[1])
            if upgraded != row[1]:
                await cursor.execute(
                    "UPDATE labeling_rules SET conditions = ? WHERE id = ?",
                    (upgraded, row[0]),
                )
