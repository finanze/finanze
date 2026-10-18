from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID

from domain import native_entities
from domain.commodity import (
    CommodityRegister,
    CommodityType,
    UpdateCommodityPosition,
    WeightUnit,
)
from domain.crypto import (
    AddressSource,
    AvailableCryptoAssetsRequest,
    ConnectCryptoWallet,
    UpdateCryptoWalletConnection,
)
from domain.dezimal import Dezimal
from domain.entity import EntityType, Feature
from domain.exception.exceptions import EntityNotFound
from domain.external_integration import ExternalIntegrationId
from domain.fetch_result import FetchOptions, FetchRequest
from domain.public_key import AddressDerivationPreviewRequest, ScriptType
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

WalletId = Annotated[UUID, Field(description="Crypto wallet ID (see list_entities).")]
CryptoEntityId = Annotated[
    UUID, Field(description="Crypto wallet entity (network) ID (see list_entities).")
]


class CommodityInput(BaseModel):
    name: str = Field(min_length=1)
    type: CommodityType
    amount: Decimal = Field(gt=0, description="Weight held.")
    unit: WeightUnit
    initial_investment: Optional[Decimal] = Field(default=None, ge=0)
    average_buy_price: Optional[Decimal] = Field(
        default=None, ge=0, description="Price per unit of weight."
    )
    currency: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Currency of initial_investment and average_buy_price.",
    )


def _optional_dezimal(value: Optional[Decimal]) -> Optional[Dezimal]:
    return Dezimal(value) if value is not None else None


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("Search crypto assets", open_world=True)
    async def search_crypto_assets(
        query: Annotated[str, Field(min_length=1, max_length=100)],
        by: Literal["symbol", "name"] = "symbol",
        page: Annotated[int, Field(ge=1)] = 1,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ):
        """Search crypto assets (coins and tokens) by symbol or name, returning provider IDs used by get_crypto_asset_details."""
        return await ucs.search_crypto_assets.execute(
            AvailableCryptoAssetsRequest(
                symbol=query if by == "symbol" else None,
                name=query if by == "name" else None,
                page=page,
                limit=limit,
            )
        )

    @registry.read("Get crypto asset details", open_world=True)
    async def get_crypto_asset_details(
        provider_id: Annotated[
            str,
            Field(description="Asset ID in the provider, from search_crypto_assets."),
        ],
        provider: ExternalIntegrationId,
    ):
        """Get details of a crypto asset from a market data provider: current price, platforms and contract addresses."""
        return await ucs.get_crypto_asset_details.execute(provider_id, provider)

    @registry.read("Get crypto wallet addresses")
    async def get_crypto_wallet_addresses(wallet_id: WalletId):
        """Get all the addresses of a connected crypto wallet, including the ones derived from an HD wallet public key."""
        return await ucs.get_crypto_wallet_addresses.execute(wallet_id)

    @registry.read("Derive crypto addresses")
    async def derive_crypto_addresses(
        entity_id: CryptoEntityId,
        xpub: Annotated[
            str, Field(description="Extended public key (xpub, ypub, zpub...).")
        ],
        script_type: Optional[ScriptType] = None,
        range: Annotated[int, Field(ge=1, le=50)] = 5,
    ):
        """Preview the first addresses derived from an HD wallet extended public key, to check it before adding the wallet."""
        entity = native_entities.get_native_by_id(entity_id, EntityType.CRYPTO_WALLET)
        if entity is None:
            raise EntityNotFound(entity_id)
        return await ucs.derive_crypto_addresses.execute(
            AddressDerivationPreviewRequest(
                xpub=xpub, entity=entity, range=range, script_type=script_type
            )
        )

    @registry.write("Add crypto wallet")
    async def add_crypto_wallet(
        entity_id: CryptoEntityId,
        name: Annotated[str, Field(min_length=1, max_length=100)],
        addresses: Annotated[
            Optional[list[str]],
            Field(description="Public addresses. Omit when providing xpub."),
        ] = None,
        xpub: Annotated[
            Optional[str],
            Field(description="HD wallet extended public key, instead of addresses."),
        ] = None,
        script_type: Annotated[
            Optional[ScriptType], Field(description="Required with xpub.")
        ] = None,
        include_wallet_tokens: Annotated[
            bool, Field(description="Also track tokens held by the addresses.")
        ] = False,
    ):
        """Connect a crypto wallet to track it by its public addresses or extended public key. Never ask for or accept private keys or seed phrases."""
        if xpub:
            if not script_type:
                raise ToolError("script_type is required with xpub.")
            source = AddressSource.DERIVED
        elif addresses:
            source = AddressSource.MANUAL
        else:
            raise ToolError("Provide addresses or xpub with script_type.")
        return await ucs.connect_crypto_wallet.execute(
            ConnectCryptoWallet(
                entity_id=entity_id,
                addresses=[] if xpub else addresses,
                name=name,
                address_source=source,
                xpub=xpub,
                script_type=script_type if xpub else None,
                include_wallet_tokens=include_wallet_tokens,
            )
        )

    @registry.write("Rename crypto wallet", idempotent=True)
    async def rename_crypto_wallet(
        wallet_id: WalletId,
        name: Annotated[str, Field(min_length=1, max_length=100)],
    ):
        """Rename a connected crypto wallet."""
        await ucs.update_crypto_wallet.execute(
            UpdateCryptoWalletConnection(id=wallet_id, name=name)
        )
        return {"updated": str(wallet_id)}

    @registry.write("Delete crypto wallet", destructive=True, idempotent=True)
    async def delete_crypto_wallet(wallet_id: WalletId):
        """Disconnect a crypto wallet and remove its tracked positions."""
        await ucs.delete_crypto_wallet.execute(wallet_id)
        return {"deleted": str(wallet_id)}

    @registry.write("Refresh crypto data", idempotent=True, open_world=True)
    async def refresh_crypto_data(
        entity_id: Annotated[
            Optional[UUID],
            Field(description="Crypto wallet entity ID. Omit to refresh all."),
        ] = None,
    ):
        """Fetch the latest balances of the connected crypto wallets from the blockchain providers."""
        result = await ucs.fetch_crypto_data.execute(
            FetchRequest(
                entity_id=entity_id,
                features=[Feature.POSITION],
                fetch_options=FetchOptions(),
            )
        )
        return {"code": result.code, "details": result.details}

    @registry.write("Save commodities", destructive=True, idempotent=True)
    async def save_commodities(
        commodities: Annotated[
            list[CommodityInput],
            Field(
                description="Complete list of commodity holdings. Holdings not included are removed."
            ),
        ],
    ):
        """Replace all the precious metal holdings (gold, silver, platinum, palladium). Get the current ones first with get_positions(product_types=[COMMODITY]) and send the full list. Market value is computed automatically."""
        await ucs.save_commodities.execute(
            UpdateCommodityPosition(
                registers=[
                    CommodityRegister(
                        name=c.name,
                        type=c.type,
                        amount=Dezimal(c.amount),
                        unit=c.unit,
                        initial_investment=_optional_dezimal(c.initial_investment),
                        average_buy_price=_optional_dezimal(c.average_buy_price),
                        currency=c.currency.upper() if c.currency else None,
                    )
                    for c in commodities
                ]
            )
        )
        return {"saved": len(commodities)}
