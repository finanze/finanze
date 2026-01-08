import {
  AvailableCryptoAssetsRequest,
  AvailableCryptoAssetsResult,
} from "@/domain"

export interface SearchCryptoAssets {
  execute(
    request: AvailableCryptoAssetsRequest,
  ): Promise<AvailableCryptoAssetsResult>
}
