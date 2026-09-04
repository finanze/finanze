import logging
from uuid import uuid4

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import (
    CryptoCurrencyType,
    CryptoFetchedPosition,
    CryptoFetchRequest,
    CryptoFetchResult,
    CryptoFetchResults,
    CryptoPositionType,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, ExternalIntegrationRequired
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.crypto.zerion.zerion_client import ZerionClient

# Zerion labels wallet-held tokens with this generic placeholder name.
ZERION_GENERIC_ASSET_NAME = "Asset"

POSITION_TYPE_MAP = {
    "wallet": CryptoPositionType.HOLDING,
    "deposit": CryptoPositionType.SUPPLIED,
    "investment": CryptoPositionType.SUPPLIED,
    "staked": CryptoPositionType.STAKED,
    "locked": CryptoPositionType.STAKED,
    "reward": CryptoPositionType.REWARD,
    "loan": CryptoPositionType.BORROWED,
}


class ZerionFetcher(CryptoEntityFetcher):
    def __init__(self, client: ZerionClient):
        self._client = client
        self._log = logging.getLogger(__name__)

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        if ExternalIntegrationId.ZERION not in request.integrations:
            raise ExternalIntegrationRequired([ExternalIntegrationId.ZERION])

        api_key = request.integrations[ExternalIntegrationId.ZERION]["api_key"]
        positions_filter = (
            "no_filter" if request.include_wallet_tokens else "only_complex"
        )

        results: dict[str, CryptoFetchResult | None] = {}
        for address in request.addresses:
            try:
                raw = await self._client.fetch_positions(
                    api_key, address, positions_filter
                )
            except AddressNotFound:
                results[address] = None
                continue

            assets: list[CryptoFetchedPosition] = []
            mapped_raw: list[dict] = []
            for item in raw:
                try:
                    assets.append(self._map_item(item))
                    mapped_raw.append(item)
                except (KeyError, TypeError, AttributeError, ValueError) as exc:
                    self._log.warning(
                        "Skipping unmappable Zerion position %s: %s",
                        item.get("id") if isinstance(item, dict) else None,
                        exc,
                    )

            if request.include_wallet_tokens:
                assets = self._dedup_receipt_holdings(assets, mapped_raw)

            results[address] = CryptoFetchResult(address=address, assets=assets)

        return CryptoFetchResults(results=results)

    @staticmethod
    def _map_item(item: dict) -> CryptoFetchedPosition:
        attributes = item["attributes"]
        position_type = POSITION_TYPE_MAP.get(
            attributes["position_type"], CryptoPositionType.SUPPLIED
        )

        chain = item["relationships"]["chain"]["data"]["id"]
        protocol = attributes.get("protocol")

        fungible_info = attributes.get("fungible_info") or {}
        symbol = fungible_info.get("symbol")
        if not symbol:
            # crypto_currency_positions.symbol is NOT NULL: a symbol-less
            # position can't be persisted, so skip it explicitly here rather
            # than relying on the pydantic ValidationError raised below to be
            # a ValueError caught by the per-item guard in fetch().
            raise ValueError(f"Zerion position {item.get('id')} has no symbol")
        raw_name = attributes.get("name")
        name = (
            raw_name
            if raw_name and raw_name != ZERION_GENERIC_ASSET_NAME
            else fungible_info.get("name")
        )
        name = name or symbol or raw_name  # crypto_currency_positions.name is NOT NULL

        fungible_icon = fungible_info.get("icon") or {}
        icon_url = fungible_icon.get("url")
        if not icon_url:
            application_metadata = attributes.get("application_metadata") or {}
            app_icon = application_metadata.get("icon") or {}
            icon_url = app_icon.get("url")

        implementation = next(
            (
                impl
                for impl in fungible_info.get("implementations") or []
                if impl.get("chain_id") == chain
            ),
            None,
        )
        address = implementation.get("address") if implementation else None
        contract_address = address.lower() if address else None
        asset_type = (
            CryptoCurrencyType.NATIVE
            if implementation is not None and not address
            else CryptoCurrencyType.TOKEN
        )

        amount = Dezimal(attributes["quantity"]["numeric"])

        value = attributes.get("value")
        market_value = Dezimal(str(value)) if value is not None else None
        currency = "EUR" if market_value is not None else None

        if position_type == CryptoPositionType.BORROWED:
            amount = -abs(amount)
            if market_value is not None:
                market_value = -abs(market_value)

        return CryptoFetchedPosition(
            id=uuid4(),
            symbol=symbol,
            balance=amount,
            type=asset_type,
            name=name,
            contract_address=contract_address,
            chain=chain,
            protocol=protocol,
            position_type=position_type,
            market_value=market_value,
            currency=currency,
            icon_url=icon_url,
        )

    @staticmethod
    def _receipt_contract_keys(raw_items: list[dict]) -> set[tuple[str, str]]:
        receipt_keys: set[tuple[str, str]] = set()
        for item in raw_items:
            attributes = item["attributes"]
            if attributes.get("position_type") == "wallet":
                continue

            receipt = attributes.get("receipt")
            if not isinstance(receipt, dict):
                continue

            # Only the receipt implementation on the position's own chain
            # duplicates a wallet holding; the same contract address on another
            # chain is a separate asset. The receipt sub-object is parsed
            # leniently so one malformed receipt can't abort the whole address.
            chain = item["relationships"]["chain"]["data"]["id"]
            fungible_info = receipt.get("fungible_info")
            if not isinstance(fungible_info, dict):
                continue
            implementations = fungible_info.get("implementations")
            if not isinstance(implementations, list):
                continue
            for implementation in implementations:
                if not isinstance(implementation, dict):
                    continue
                address = implementation.get("address")
                if (
                    implementation.get("chain_id") == chain
                    and isinstance(address, str)
                    and address
                ):
                    receipt_keys.add((chain, address.lower()))

        return receipt_keys

    @classmethod
    def _dedup_receipt_holdings(
        cls, assets: list[CryptoFetchedPosition], raw_items: list[dict]
    ) -> list[CryptoFetchedPosition]:
        receipt_keys = cls._receipt_contract_keys(raw_items)
        if not receipt_keys:
            return assets

        return [
            asset
            for asset in assets
            if not (
                asset.position_type == CryptoPositionType.HOLDING
                and asset.chain is not None
                and asset.contract_address is not None
                and (asset.chain, asset.contract_address) in receipt_keys
            )
        ]
