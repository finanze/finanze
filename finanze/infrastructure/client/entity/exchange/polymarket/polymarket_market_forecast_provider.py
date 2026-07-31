from application.ports.market_forecast_provider import (
    MarketForecastAccountData,
    MarketForecastProvider,
)
from domain.entity_login import EntityLoginParams, LoginResultCode
from infrastructure.client.entity.exchange.polymarket.polymarket_client import (
    PolymarketClient,
)


class PolymarketMarketForecastProvider(MarketForecastProvider):
    async def get_open_positions(
        self, login_params: EntityLoginParams
    ) -> MarketForecastAccountData | None:
        client = PolymarketClient()
        if not await self._setup_client(client, login_params):
            return None

        return MarketForecastAccountData(
            wallet_address=client.wallet_address,
            profile=client.profile,
            open_positions=await client.get_positions(),
        )

    async def get_closed_positions(
        self, login_params: EntityLoginParams
    ) -> MarketForecastAccountData | None:
        client = PolymarketClient()
        if not await self._setup_client(client, login_params):
            return None

        return MarketForecastAccountData(
            wallet_address=client.wallet_address,
            profile=client.profile,
            closed_positions=await client.get_closed_positions(),
        )

    async def get_pnl_history(
        self, login_params: EntityLoginParams, interval: str = "all"
    ) -> MarketForecastAccountData | None:
        client = PolymarketClient()
        if not await self._setup_client(client, login_params):
            return None

        return MarketForecastAccountData(
            wallet_address=client.wallet_address,
            profile=client.profile,
            pnl_history=await client.get_user_pnl(interval=interval),
        )

    @staticmethod
    async def _setup_client(
        client: PolymarketClient,
        login_params: EntityLoginParams,
    ) -> bool:
        result = await client.setup(login_params)
        return result.code == LoginResultCode.CREATED
