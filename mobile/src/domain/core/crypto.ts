import { ExternalIntegrationId } from "./externalIntegration"
import { Dezimal } from "@/domain/dezimal"

export enum CryptoCurrencyType {
  NATIVE = "NATIVE",
  TOKEN = "TOKEN",
}

export interface CryptoAsset {
  name: string
  symbol: string | null
  iconUrls: string[] | null
  externalIds: Record<string, string>
  id?: string | null
}

export interface CryptoWalletConnection {
  id: string
  entityId: string
  address: string
  name: string
}

export interface CryptoFetchRequest {
  address: string
  integrations: Partial<Record<ExternalIntegrationId, Record<string, string>>>
  connectionId?: string | null
}

export interface ConnectCryptoWallet {
  entityId: string
  addresses: string[]
  name: string
}

export enum CryptoWalletConnectionFailureCode {
  ADDRESS_ALREADY_EXISTS = "ADDRESS_ALREADY_EXISTS",
  ADDRESS_NOT_FOUND = "ADDRESS_NOT_FOUND",
  TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS",
  UNEXPECTED_ERROR = "UNEXPECTED_ERROR",
}

export interface CryptoWalletConnectionResult {
  failed: Record<string, CryptoWalletConnectionFailureCode>
}

export interface UpdateCryptoWalletConnection {
  id: string
  name: string
}

export interface CryptoPlatform {
  providerId: string
  name: string
  iconUrl: string | null
}

export interface CryptoAssetPlatform {
  providerId: string
  name: string
  contractAddress: string | null
  iconUrl: string | null
  relatedEntityId: string | null
}

export interface AvailableCryptoAsset {
  name: string
  symbol: string
  platforms: CryptoAssetPlatform[]
  provider: ExternalIntegrationId
  providerId: string
}

export interface AvailableCryptoAssets {
  assets: AvailableCryptoAsset[]
}

export interface AvailableCryptoAssetsRequest {
  symbol: string | null
  name: string | null
  page?: number
  limit?: number
}

export interface AvailableCryptoAssetsResult {
  provider: ExternalIntegrationId
  assets: AvailableCryptoAsset[]
  page: number
  limit: number
  total: number
}

export interface CryptoAssetDetails {
  name: string
  symbol: string
  platforms: CryptoAssetPlatform[]
  provider: ExternalIntegrationId
  providerId: string
  price: Record<string, Dezimal>
  type: CryptoCurrencyType
  iconUrl: string | null
}
