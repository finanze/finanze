from uuid import UUID

from application.ports.credentials_port import CredentialsPort
from application.ports.entity_account_port import EntityAccountPort
from domain.entity_account import EntityAccount
from domain.entity_login import EntityLoginParams
from domain.native_entities import POLYMARKET
from domain.public_keychain import PublicKeychain


async def resolve_market_forecast_accounts(
    entity_account_port: EntityAccountPort,
    entity_account_ids: list[UUID] | None,
) -> list[EntityAccount]:
    accounts = (
        await entity_account_port.get_by_ids(entity_account_ids)
        if entity_account_ids
        else await entity_account_port.get_by_entity_id(POLYMARKET.id)
    )
    return [account for account in accounts if account.entity_id == POLYMARKET.id]


async def build_market_forecast_login_params(
    credentials_port: CredentialsPort,
    entity_account_id: UUID,
) -> EntityLoginParams | None:
    credentials = await credentials_port.get(entity_account_id)
    if not credentials:
        return None

    return EntityLoginParams(
        credentials=credentials,
        keychain=PublicKeychain({}),
    )


def build_market_forecast_account_payload(
    account: EntityAccount,
    wallet_address: str,
    profile: dict | None,
) -> dict:
    return {
        "entity_account_id": str(account.id),
        "entity_id": str(account.entity_id),
        "account_name": account.name,
        "wallet_address": wallet_address,
        "profile": profile,
    }


def enrich_market_forecast_items(
    items: list[dict],
    account: EntityAccount,
    wallet_address: str,
) -> list[dict]:
    return [
        {
            **item,
            "entity_account_id": str(account.id),
            "wallet_address": wallet_address,
        }
        for item in items
    ]
