from enum import Enum


class SettingsQueries(str, Enum):
    GET_ALL = 'SELECT "key", value, updated_at FROM settings'

    UPSERT = (
        'INSERT OR REPLACE INTO settings ("key", value, updated_at) VALUES (?, ?, ?)'
    )

    DELETE_ALL = "DELETE FROM settings"

    @staticmethod
    def get_by_keys(count: int) -> str:
        placeholders = ",".join("?" for _ in range(count))
        return f'SELECT "key", value, updated_at FROM settings WHERE "key" IN ({placeholders})'
