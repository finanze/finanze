import json

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

LEGACY_ENTRY_KEYS = ("provider", "model", "upstreamProvider")


def _labeling_entries(external: dict) -> list[dict]:
    providers = external.get("providers")
    if not isinstance(providers, list):
        providers = [{key: external.get(key) for key in LEGACY_ENTRY_KEYS}]

    entries, seen = [], set()
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider, model = item.get("provider"), item.get("model")
        if not isinstance(provider, str) or not isinstance(model, str):
            continue
        if not provider.strip() or not model.strip():
            continue
        upstream = item.get("upstreamProvider") or None
        identity = (provider.strip(), model.strip(), upstream)
        if identity in seen:
            continue
        seen.add(identity)
        entries.append(
            {
                "provider": identity[0],
                "model": identity[1],
                "upstreamProvider": upstream,
            }
        )
    return entries


def upgrade_sections(labeling: dict) -> tuple[dict, dict] | None:
    external = labeling.get("external")
    if not isinstance(external, dict):
        return None
    entries = _labeling_entries(external)
    if not entries:
        return None
    external = {
        key: value for key, value in external.items() if key not in LEGACY_ENTRY_KEYS
    }
    external["providers"] = []
    return {**labeling, "external": external}, {"providers": entries}


class V01204AISettings(DBVersionMigration):
    @property
    def name(self):
        return "v0.12.0:4_ai_settings"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            'SELECT "key", value, updated_at FROM settings WHERE "key" IN (?, ?)',
            ("labeling", "ai"),
        )
        rows = {row[0]: (row[1], row[2]) for row in await cursor.fetchall()}
        if "ai" in rows or "labeling" not in rows:
            return

        raw, updated_at = rows["labeling"]
        try:
            labeling = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(labeling, dict):
            return

        upgraded = upgrade_sections(labeling)
        if upgraded is None:
            return
        labeling, ai = upgraded
        await cursor.execute(
            'INSERT INTO settings ("key", value, updated_at) VALUES (?, ?, ?)',
            ("ai", json.dumps(ai), updated_at),
        )
        await cursor.execute(
            'UPDATE settings SET value = ? WHERE "key" = ?',
            (json.dumps(labeling), "labeling"),
        )
