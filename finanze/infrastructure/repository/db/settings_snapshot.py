import logging

GET_SETTINGS_ROWS = 'SELECT "key", value, updated_at FROM settings'
COUNT_SETTINGS_ROWS = "SELECT COUNT(*) FROM settings"
INSERT_SETTINGS_ROW = (
    'INSERT OR REPLACE INTO settings ("key", value, updated_at) VALUES (?, ?, ?)'
)

_log = logging.getLogger(__name__)


async def read_settings_rows(client) -> list[tuple[str, str, str]]:
    try:
        async with client.read() as cursor:
            await cursor.execute(GET_SETTINGS_ROWS)
            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2]) for row in rows]
    except Exception as e:
        _log.warning(f"Could not read settings rows: {e}")
        return []


async def restore_settings_rows_if_empty(
    client, rows: list[tuple[str, str, str]]
) -> bool:
    if not rows:
        return False

    async with client.read() as cursor:
        await cursor.execute(COUNT_SETTINGS_ROWS)
        count = (await cursor.fetchone())[0]

    if count:
        return False

    async with client.tx() as cursor:
        for row in rows:
            await cursor.execute(INSERT_SETTINGS_ROW, row)
    return True
