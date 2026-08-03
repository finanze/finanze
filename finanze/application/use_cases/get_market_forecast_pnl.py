from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from application.ports.market_forecast_provider import MarketForecastProvider
from domain.entity_account import EntityAccount
from domain.entity_login import EntityLoginParams
from domain.market_forecast import (
    MarketForecastAccountSummary,
    MarketForecastPnlAccount,
    MarketForecastPnlPoint,
    MarketForecastPnlResponse,
)
from domain.native_entities import POLYMARKET
from domain.public_keychain import PublicKeychain
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
    ) -> MarketForecastPnlResponse:
        accounts = await self._resolve_accounts(entity_account_ids)
        account_payloads = []
        for account in accounts:
            try:
                account_payloads.append(
                    await self._fetch_account_data(account, interval)
                )
            except Exception as error:
                account_payloads.append(error)

        valid_payloads = [
            payload
            for payload in account_payloads
            if payload and not isinstance(payload, Exception)
        ]
        return MarketForecastPnlResponse(
            interval=interval,
            accounts=valid_payloads,
            pnl_history=[
                point for account in valid_payloads for point in account.pnl_history
            ],
        )

    async def _resolve_accounts(
        self, entity_account_ids: list[UUID] | None
    ) -> list[EntityAccount]:
        accounts = (
            await self._entity_account_port.get_by_ids(entity_account_ids)
            if entity_account_ids
            else await self._entity_account_port.get_by_entity_id(POLYMARKET.id)
        )
        return [account for account in accounts if account.entity_id == POLYMARKET.id]

    async def _fetch_account_data(
        self, account: EntityAccount, interval: str
    ) -> MarketForecastPnlAccount | None:
        credentials = await self._credentials_port.get(account.id)
        if not credentials:
            return None

        login_params = EntityLoginParams(
            credentials=credentials,
            keychain=PublicKeychain({}),
        )
        account_data = await self._provider.get_pnl_history(
            login_params,
            interval=interval,
        )
        if not account_data:
            return None

        summary = MarketForecastAccountSummary(
            entity_account_id=account.id,
            entity_id=account.entity_id,
            account_name=account.name,
            wallet_address=account_data.wallet_address,
            currency=account_data.currency,
            profile=account_data.profile,
        )
        points = [
            MarketForecastPnlPoint(
                timestamp=point.timestamp,
                value=point.value,
                currency=point.currency,
                entity_account_id=account.id,
                wallet_address=account_data.wallet_address,
            )
            for point in account_data.pnl_history or []
        ]
        return MarketForecastPnlAccount(**summary.__dict__, pnl_history=points)
