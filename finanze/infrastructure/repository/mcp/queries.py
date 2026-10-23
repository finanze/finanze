from enum import Enum


class McpConfigQueries(str, Enum):
    GET = "SELECT enabled, allow_writes, token, category_access FROM mcp_config WHERE id = 1"

    UPSERT = """
        INSERT INTO mcp_config (id, enabled, allow_writes, token, category_access, updated_at)
        VALUES (1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            enabled = excluded.enabled,
            allow_writes = excluded.allow_writes,
            token = excluded.token,
            category_access = excluded.category_access,
            updated_at = excluded.updated_at
    """
