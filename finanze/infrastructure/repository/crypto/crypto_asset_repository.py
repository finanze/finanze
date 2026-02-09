import json
from typing import Optional
from uuid import UUID

from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from domain.crypto import CryptoAsset
from infrastructure.repository.crypto.queries import CryptoAssetQueries
from infrastructure.repository.db.client import DBClient


def map_crypto_asset_row(row) -> CryptoAsset:
    icon_urls = []
    if row["icon_urls"]:
        try:
            icon_urls = json.loads(row["icon_urls"]) or []
        except Exception:
            icon_urls = []
    external_ids = {}
    if row["external_ids"]:
        try:
            external_ids = json.loads(row["external_ids"]) or {}
        except Exception:
            external_ids = {}

    return CryptoAsset(
        id=UUID(row["id"]),
        name=row["name"],
        symbol=row["symbol"],
        icon_urls=icon_urls,
        external_ids=external_ids,
    )


class CryptoAssetRegistryRepository(CryptoAssetRegistryPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_by_symbol(self, symbol: str) -> Optional[CryptoAsset]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                CryptoAssetQueries.GET_BY_SYMBOL,
                (symbol,),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return map_crypto_asset_row(row)

    async def save(self, asset: CryptoAsset):
        icon_urls_json = json.dumps(asset.icon_urls) if asset.icon_urls else None
        external_ids_json = (
            json.dumps(asset.external_ids) if asset.external_ids else json.dumps({})
        )

        async with self._db_client.tx() as cursor:
            await cursor.execute(
                CryptoAssetQueries.INSERT,
                (
                    str(asset.id),
                    asset.name,
                    asset.symbol,
                    icon_urls_json,
                    external_ids_json,
                ),
            )
