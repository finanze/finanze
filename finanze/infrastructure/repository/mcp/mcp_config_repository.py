import json
from dataclasses import asdict
from datetime import datetime

from application.ports.mcp_config_port import McpConfigPort
from dateutil.tz import tzlocal
from domain.mcp import McpConfig
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.mcp.queries import McpConfigQueries


class McpConfigRepository(McpConfigPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get(self) -> McpConfig:
        async with self._db_client.read() as cursor:
            await cursor.execute(McpConfigQueries.GET)
            row = await cursor.fetchone()
        if row is None:
            return McpConfig()
        return McpConfig(
            enabled=bool(row["enabled"]),
            read_only=not bool(row["allow_writes"]),
            token=row["token"],
            category_access=json.loads(row["category_access"]),
        )

    async def save(self, config: McpConfig):
        async with self._db_client.tx(skip_last_update=True) as cursor:
            await cursor.execute(
                McpConfigQueries.UPSERT,
                (
                    config.enabled,
                    not config.read_only,
                    config.token,
                    json.dumps(
                        {
                            category.value: asdict(access)
                            for category, access in config.category_access.items()
                        }
                    ),
                    datetime.now(tzlocal()).isoformat(),
                ),
            )
