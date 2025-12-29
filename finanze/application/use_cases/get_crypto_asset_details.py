from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.entity_port import EntityPort
from domain.constants import SUPPORTED_CURRENCIES
from domain.crypto import CryptoAssetDetails, CryptoAssetPlatform
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.get_crypto_asset_details import GetCryptoAssetDetails


class GetCryptoAssetDetailsImpl(GetCryptoAssetDetails):
    def __init__(
        self,
        crypto_asset_info_provider: CryptoAssetInfoProvider,
        entity_port: EntityPort,
    ):
        self._provider = crypto_asset_info_provider
        self._entity_port = entity_port

    def execute(
        self, provider_id: str, provider: ExternalIntegrationId
    ) -> CryptoAssetDetails:
        if provider != ExternalIntegrationId.COINGECKO:
            raise ValueError(f"Unsupported provider: {provider}")

        details = self._provider.get_asset_details(
            provider_id=provider_id,
            currencies=SUPPORTED_CURRENCIES,
        )

        if not details.platforms:
            fake_platform = CryptoAssetPlatform(
                provider_id=details.provider_id,
                name=details.name,
                contract_address=None,
                icon_url=details.icon_url,
                related_entity_id=None,
            )
            details.platforms.append(fake_platform)

        for platform in details.platforms:
            entity = self._provider.get_native_entity_by_platform(
                platform.provider_id, provider
            )

            if entity is None:
                natural_id = f"{provider.value.lower()}:{platform.provider_id}"
                entity = self._entity_port.get_by_natural_id(natural_id)

            if entity:
                platform.related_entity_id = entity.id

        return details
