import {
  AvailableCryptoAsset,
  CryptoAsset,
  CryptoAssetDetails,
  CryptoPlatform,
  Entity,
  ExternalIntegrationId,
} from "@/domain"
import { Dezimal } from "@/domain/dezimal"

export interface CryptoAssetInfoProvider {
  getPrice(symbol: string, fiatIso: string, kwargs: any): Promise<Dezimal>
  getMultiplePricesBySymbol(
    symbols: string[],
    fiatIsos: string[],
    kwargs: any,
  ): Promise<Record<string, Record<string, Dezimal>>>
  getPricesByAddresses(
    addresses: string[],
    fiatIsos: string[],
    kwargs: any,
  ): Promise<Record<string, Record<string, Dezimal>>>
  getBySymbol(symbol: string): Promise<CryptoAsset[]>
  getMultipleOverviewByAddresses(
    addresses: string[],
  ): Promise<Record<string, CryptoAsset>>
  assetLookup(
    symbol?: string | null,
    name?: string | null,
  ): Promise<AvailableCryptoAsset[]>
  getAssetPlatforms(): Promise<Record<string, CryptoPlatform>>
  getAssetDetails(
    providerId: string,
    currencies: string[],
    provider?: ExternalIntegrationId,
  ): Promise<CryptoAssetDetails>
  getNativeEntityByPlatform(
    providerId: string,
    provider: ExternalIntegrationId,
  ): Promise<Entity | null>
}
