from datetime import datetime
from typing import Annotated

from dateutil.tz import tzlocal
from domain.available_sources import FinancialEntityStatus
from domain.entity import EntityOrigin
from domain.settings import SettingsSection
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases


def register(registry: ToolRegistry, ucs: McpUseCases, version: str):
    @registry.read("Get context")
    async def get_context():
        """Get today's date, local timezone, the user's default currency and commodity weight unit, the Finanze version and whether access is read-only. Call it first to interpret dates and amounts."""
        settings = await ucs.get_settings.execute({SettingsSection.GENERAL})
        now = datetime.now(tzlocal())
        return {
            "today": now.date(),
            "now": now.replace(microsecond=0),
            "timezone": now.tzname(),
            "default_currency": settings.general.defaultCurrency,
            "default_commodity_weight_unit": settings.general.defaultCommodityWeightUnit,
            "version": version,
            "read_only": not registry.writes_enabled,
        }

    @registry.read("List entities")
    async def list_entities(
        include_available: Annotated[
            bool,
            Field(
                description="Also include supported entities the user has not set up."
            ),
        ] = False,
    ):
        """List the user's financial entities (banks, brokers, crypto wallets, exchanges, manual entities) with IDs, type, origin, status, fetchable features, last fetch dates, login accounts (needed by fetch_entity_data) and connected crypto wallets."""
        sources = await ucs.get_available_entities.execute()
        result = []
        for source in sources.entities:
            in_use = (
                source.status != FinancialEntityStatus.DISCONNECTED
                or bool(source.connected)
                or source.origin == EntityOrigin.MANUAL
            )
            if not include_available and not in_use:
                continue
            result.append(
                {
                    "id": source.id,
                    "name": source.name,
                    "type": source.type,
                    "origin": source.origin,
                    "status": source.status,
                    "provider": source.provider,
                    "features": source.features,
                    "last_fetch": source.last_fetch,
                    "last_import": source.virtual_features,
                    "natively_supported_products": source.natively_supported_products,
                    "required_integrations": source.required_external_integrations,
                    "accounts": source.accounts,
                    "wallets": [
                        {
                            "id": wallet.id,
                            "name": wallet.name,
                            "address_source": wallet.address_source,
                            "addresses": wallet.addresses,
                            "hd_wallet": wallet.hd_wallet is not None,
                            "include_wallet_tokens": wallet.include_wallet_tokens,
                        }
                        for wallet in source.connected or []
                    ],
                }
            )
        return result
