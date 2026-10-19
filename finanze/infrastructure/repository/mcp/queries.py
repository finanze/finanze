from enum import Enum


class McpConfigQueries(str, Enum):
    GET = "SELECT enabled, allow_writes, token FROM mcp_config WHERE id = 1"

    UPSERT = """
        INSERT INTO mcp_config (id, enabled, allow_writes, token, updated_at)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            enabled = excluded.enabled,
            allow_writes = excluded.allow_writes,
            token = excluded.token,
            updated_at = excluded.updated_at
    """
