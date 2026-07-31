import asyncio
from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from application.ports.market_forecast_provider import MarketForecastProvider
from application.use_cases.market_forecast_common import (
    build_market_forecast_account_payload,
    build_market_forecast_login_params,
    resolve_market_forecast_accounts,
)
from domain.use_cases.get_market_forecast_pnl import GetMarketForecastPnl


class GetMarketForecastPnlImpl(GetMarketForecastPnl):
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
        interval: str = "all",
    ) -> dict:
        accounts = await resolve_market_forecast_accounts(
            self._entity_account_port,
            entity_account_ids,
        )
        account_payloads = await asyncio.gather(
            *(self._fetch_account_data(account, interval) for account in accounts),
            return_exceptions=True,
        )

        valid_payloads = [
            payload
            for payload in account_payloads
            if payload and not isinstance(payload, Exception)
        ]
        return {
            "interval": interval,
            "accounts": valid_payloads,
            "pnl_history": [
                point for payload in valid_payloads for point in payload["pnl_history"]
            ],
        }

    async def _fetch_account_data(self, account, interval: str) -> dict | None:
        login_params = await build_market_forecast_login_params(
            self._credentials_port,
            account.id,
        )
        if not login_params:
            return None

        account_data = await self._provider.get_pnl_history(
            login_params,
            interval=interval,
        )
        if not account_data:
            return None

        return {
            **build_market_forecast_account_payload(
                account,
                account_data.wallet_address,
                account_data.profile,
            ),
            "pnl_history": [
                {
                    **point,
                    "entity_account_id": str(account.id),
                    "wallet_address": account_data.wallet_address,
                }
                for point in account_data.pnl_history
            ],
        }
