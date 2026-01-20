import json

from application.ports.config_port import ConfigPort
from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE external_integrations
          ADD COLUMN payload JSON;
      """


class V0702ExternalIntegrationsMigration(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.7.0:2_external_integrations_migration"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)

        config_port: ConfigPort | None = context.config
        if not config_port:
            return

        config = await config_port.raw_load()
        if config is None or "integrations" not in config:
            return

        integrations_entry = config["integrations"]
        google_sheets_entry = integrations_entry.get("sheets", {}).get(
            "credentials", {}
        )
        gs_client_id, gs_client_secret = (
            google_sheets_entry.get("client_id"),
            google_sheets_entry.get("client_secret"),
        )
        if gs_client_id and gs_client_secret:
            sheets_payload = {
                "client_id": gs_client_id,
                "client_secret": gs_client_secret,
            }
            await self.migrate_active(cursor, "GOOGLE_SHEETS", sheets_payload)
        else:
            await self.keep_off(cursor, "GOOGLE_SHEETS")

        etherscan_entry = integrations_entry.get("etherscan", {})
        etherscan_api_key = etherscan_entry.get("api_key")
        if etherscan_api_key:
            etherscan_payload = {
                "api_key": etherscan_api_key,
            }
            await self.migrate_active(cursor, "ETHERSCAN", etherscan_payload)
        else:
            await self.keep_off(cursor, "ETHERSCAN")

        gocardless_entry = integrations_entry.get("gocardless", {})
        gc_secret_id, gc_secret_key = (
            gocardless_entry.get("secret_id"),
            gocardless_entry.get("secret_key"),
        )
        if gc_secret_id and gc_secret_key:
            gocardless_payload = {
                "secret_id": gc_secret_id,
                "secret_key": gc_secret_key,
            }
            await self.migrate_active(cursor, "GOCARDLESS", gocardless_payload)
        else:
            await self.keep_off(cursor, "GOCARDLESS")

    async def migrate_active(
        self, cursor: DBCursor, integration_id: str, payload: dict
    ):
        update_query = """
                       UPDATE external_integrations
                       SET payload = ?,
                           status  = 'ON'
                       WHERE id = ?
                         AND status = 'ON';
                       """
        await cursor.execute(update_query, (json.dumps(payload), integration_id))

    async def keep_off(self, cursor: DBCursor, integration_id: str):
        update_query = """
                       UPDATE external_integrations
                       SET status = 'OFF'
                       WHERE id = ?
                         AND status = 'ON';
                       """
        await cursor.execute(update_query, (integration_id,))
