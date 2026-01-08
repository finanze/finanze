import { CryptoAssetDetails, ExternalIntegrationId } from "@/domain"

export interface GetCryptoAssetDetails {
  execute(
    providerId: string,
    provider: ExternalIntegrationId,
  ): Promise<CryptoAssetDetails>
}
