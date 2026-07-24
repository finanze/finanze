import asyncio
from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from domain.entity_login import EntityLoginParams, LoginResultCode
from domain.native_entities import POLYMARKET
from domain.public_keychain import PublicKeychain
from domain.use_cases.get_polymarket_bets import GetPolymarketBets
from infrastructure.client.entity.exchange.polymarket.polymarket_client import (
    PolymarketClient,
)


class GetPolymarketBetsImpl(GetPolymarketBets):
    def __init__(
        self,
        entity_account_port: EntityAccountPort,
        credentials_port: CredentialsPort,
    ):
        self._entity_account_port = entity_account_port
        self._credentials_port = credentials_port

    async def execute(
        self,
        entity_account_ids: list[UUID] | None = None,
        interval: str = "all",
    ) -> dict:
        accounts = await self._resolve_accounts(entity_account_ids)
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
            "open_positions": [
                position
                for payload in valid_payloads
                for position in payload["open_positions"]
            ],
            "closed_positions": [
                position
                for payload in valid_payloads
                for position in payload["closed_positions"]
            ],
            "pnl_history": [
                point for payload in valid_payloads for point in payload["pnl_history"]
            ],
        }

    async def _resolve_accounts(self, entity_account_ids: list[UUID] | None) -> list:
        accounts = (
            await self._entity_account_port.get_by_ids(entity_account_ids)
            if entity_account_ids
            else await self._entity_account_port.get_by_entity_id(POLYMARKET.id)
        )
        return [account for account in accounts if account.entity_id == POLYMARKET.id]

    async def _fetch_account_data(self, account, interval: str) -> dict | None:
        credentials = await self._credentials_port.get(account.id)
        if not credentials:
            return None

        client = PolymarketClient()
        result = await client.setup(
            EntityLoginParams(
                credentials=credentials,
                keychain=PublicKeychain({}),
            )
        )
        if result.code != LoginResultCode.CREATED:
            return None

        open_positions, closed_positions, pnl_history = await asyncio.gather(
            client.get_positions(),
            client.get_closed_positions(),
            client.get_user_pnl(interval=interval),
        )

        return {
            "entity_account_id": str(account.id),
            "entity_id": str(account.entity_id),
            "account_name": account.name,
            "wallet_address": client.wallet_address,
            "profile": client.profile,
            "open_positions": [
                {
                    **position,
                    "entity_account_id": str(account.id),
                    "wallet_address": client.wallet_address,
                }
                for position in open_positions
            ],
            "closed_positions": [
                {
                    **position,
                    "entity_account_id": str(account.id),
                    "wallet_address": client.wallet_address,
                }
                for position in closed_positions
            ],
            "pnl_history": [
                {
                    **point,
                    "entity_account_id": str(account.id),
                    "wallet_address": client.wallet_address,
                }
                for point in pnl_history
            ],
        }
