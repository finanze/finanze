import asyncio
from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from application.ports.market_forecast_provider import MarketForecastProvider
from application.use_cases.market_forecast_common import (
    build_market_forecast_account_payload,
    build_market_forecast_login_params,
    enrich_market_forecast_items,
    resolve_market_forecast_accounts,
)
from domain.use_cases.get_market_forecast_closed_positions import (
    GetMarketForecastClosedPositions,
)


class GetMarketForecastClosedPositionsImpl(GetMarketForecastClosedPositions):
    def __init__(
        self,
        entity_account_port: EntityAccountPort,
        credentials_port: CredentialsPort,
        provider: MarketForecastProvider,
    ):
        self._entity_account_port = entity_account_port
        self._credentials_port = credentials_port
        self._provider = provider

    async def execute(
        self,
        entity_account_ids: list[UUID] | None = None,
    ) -> dict:
        accounts = await resolve_market_forecast_accounts(
            self._entity_account_port,
            entity_account_ids,
        )
        account_payloads = await asyncio.gather(
            *(self._fetch_account_data(account) for account in accounts),
            return_exceptions=True,
        )

        valid_payloads = [
            payload
            for payload in account_payloads
            if payload and not isinstance(payload, Exception)
        ]
        return {
            "accounts": valid_payloads,
            "closed_positions": [
                position
                for payload in valid_payloads
                for position in payload["closed_positions"]
            ],
        }

    async def _fetch_account_data(self, account) -> dict | None:
        login_params = await build_market_forecast_login_params(
            self._credentials_port,
            account.id,
        )
        if not login_params:
            return None

        account_data = await self._provider.get_closed_positions(login_params)
        if not account_data:
            return None

        return {
            **build_market_forecast_account_payload(
                account,
                account_data.wallet_address,
                account_data.profile,
            ),
            "closed_positions": enrich_market_forecast_items(
                account_data.closed_positions,
                account,
                account_data.wallet_address,
            ),
        }
