from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from domain.crypto import (
    AvailableCryptoAssetsRequest,
    AvailableCryptoAssetsResult,
)
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.search_crypto_assets import SearchCryptoAssets


class SearchCryptoAssetsImpl(SearchCryptoAssets):
    def __init__(self, crypto_asset_info_provider: CryptoAssetInfoProvider):
        self._provider = crypto_asset_info_provider

    def execute(
        self, request: AvailableCryptoAssetsRequest
    ) -> AvailableCryptoAssetsResult:
        if not request.symbol and not request.name:
            return AvailableCryptoAssetsResult(
                provider=ExternalIntegrationId.COINGECKO,
                assets=[],
                page=request.page,
                limit=request.limit,
                total=0,
            )

        all_matches = self._provider.asset_lookup(
            symbol=request.symbol, name=request.name
        )
        total = len(all_matches)

        start = (request.page - 1) * request.limit
        end = start + request.limit
        page_assets = all_matches[start:end]

        return AvailableCryptoAssetsResult(
            provider=ExternalIntegrationId.COINGECKO,
            assets=page_assets,
            page=request.page,
            limit=request.limit,
            total=total,
        )
