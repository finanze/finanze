import { Entity, EntityOrigin, EntityType, Feature } from "./core/entity"
import {
  CredentialType,
  EntitySessionCategory,
  EntitySetupLoginType,
  NativeCryptoWalletEntity,
  NativeFinancialEntity,
  PinDetails,
} from "./core/nativeEntity"
import { ExternalIntegrationId } from "./core/externalIntegration"
import { ProductType } from "./core/globalPosition"

const pin = (positions: number): PinDetails => ({ positions })

export const MY_INVESTOR: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000001",
  name: "MyInvestor",
  naturalId: "BACAESMM",
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [
    Feature.POSITION,
    Feature.AUTO_CONTRIBUTIONS,
    Feature.TRANSACTIONS,
  ],
  products: [
    ProductType.ACCOUNT,
    ProductType.CARD,
    ProductType.STOCK_ETF,
    ProductType.FUND,
    ProductType.FUND_PORTFOLIO,
    ProductType.DEPOSIT,
  ],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.UNDEFINED,
  pin: pin(6),
  credentialsTemplate: {
    user: CredentialType.ID,
    password: CredentialType.PASSWORD,
  },
  iconUrl: null,
}

export const UNICAJA: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000002",
  name: "Unicaja",
  naturalId: "UCJAES2M",
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION, Feature.AUTO_CONTRIBUTIONS],
  products: [ProductType.ACCOUNT, ProductType.CARD, ProductType.LOAN],
  setupLoginType: EntitySetupLoginType.MANUAL,
  sessionCategory: EntitySessionCategory.UNDEFINED,
  credentialsTemplate: {
    user: CredentialType.ID,
    password: CredentialType.PASSWORD,
    abck: CredentialType.INTERNAL,
  },
  iconUrl: null,
}

export const TRADE_REPUBLIC: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000003",
  name: "Trade Republic",
  naturalId: "TRBKDEBB",
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [
    Feature.POSITION,
    Feature.TRANSACTIONS,
    Feature.AUTO_CONTRIBUTIONS,
  ],
  products: [
    ProductType.ACCOUNT,
    ProductType.STOCK_ETF,
    ProductType.FUND,
    ProductType.CRYPTO,
  ],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.SHORT,
  pin: pin(4),
  credentialsTemplate: {
    phone: CredentialType.PHONE,
    password: CredentialType.PIN,
  },
  iconUrl: null,
}

export const URBANITAE: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000004",
  name: "Urbanitae",
  naturalId: null,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
  products: [ProductType.ACCOUNT, ProductType.REAL_ESTATE_CF],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.UNDEFINED,
  credentialsTemplate: {
    user: CredentialType.EMAIL,
    password: CredentialType.PASSWORD,
  },
  iconUrl: null,
}

export const WECITY: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000005",
  name: "Wecity",
  naturalId: null,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
  products: [ProductType.ACCOUNT, ProductType.REAL_ESTATE_CF],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.MEDIUM,
  pin: pin(6),
  credentialsTemplate: {
    user: CredentialType.EMAIL,
    password: CredentialType.PASSWORD,
  },
  iconUrl: null,
}

export const SEGO: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000006",
  name: "SEGO",
  naturalId: null,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
  products: [ProductType.ACCOUNT, ProductType.FACTORING],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.MEDIUM,
  pin: pin(6),
  credentialsTemplate: {
    user: CredentialType.EMAIL,
    password: CredentialType.PASSWORD,
  },
  iconUrl: null,
}

export const MINTOS: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000007",
  name: "Mintos",
  naturalId: null,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION],
  products: [ProductType.ACCOUNT, ProductType.CROWDLENDING],
  setupLoginType: EntitySetupLoginType.MANUAL,
  sessionCategory: EntitySessionCategory.NONE,
  credentialsTemplate: {
    user: CredentialType.EMAIL,
    password: CredentialType.PASSWORD,
    cookie: CredentialType.INTERNAL_TEMP,
  },
  iconUrl: null,
}

export const F24: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000008",
  name: "Freedom24",
  naturalId: null,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION, Feature.TRANSACTIONS],
  products: [ProductType.ACCOUNT, ProductType.DEPOSIT],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.UNDEFINED,
  credentialsTemplate: {
    user: CredentialType.EMAIL,
    password: CredentialType.PASSWORD,
  },
  iconUrl: null,
}

export const INDEXA_CAPITAL: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000009",
  name: "Indexa Capital",
  naturalId: null,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION, Feature.TRANSACTIONS],
  products: [ProductType.ACCOUNT, ProductType.FUND, ProductType.FUND_PORTFOLIO],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.UNDEFINED,
  credentialsTemplate: { token: CredentialType.API_TOKEN },
  iconUrl: null,
}

export const ING: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000010",
  name: "ING",
  naturalId: "INGDESMM",
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [
    Feature.POSITION,
    Feature.TRANSACTIONS,
    Feature.AUTO_CONTRIBUTIONS,
  ],
  products: [
    ProductType.ACCOUNT,
    ProductType.CARD,
    ProductType.STOCK_ETF,
    ProductType.FUND,
    ProductType.FUND_PORTFOLIO,
    ProductType.DEPOSIT,
  ],
  setupLoginType: EntitySetupLoginType.MANUAL,
  sessionCategory: EntitySessionCategory.NONE,
  credentialsTemplate: {
    genomaCookie: CredentialType.INTERNAL_TEMP,
    genomaSessionId: CredentialType.INTERNAL_TEMP,
    apiCookie: CredentialType.INTERNAL_TEMP,
    apiAuth: CredentialType.INTERNAL_TEMP,
    apiExtendedSessionCtx: CredentialType.INTERNAL_TEMP,
  },
  iconUrl: null,
}

export const CAJAMAR: NativeFinancialEntity = {
  id: "e0000000-0000-0000-0000-000000000011",
  name: "Grupo Cajamar",
  naturalId: "BCCAESMM",
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  features: [Feature.POSITION],
  products: [ProductType.ACCOUNT, ProductType.CARD, ProductType.LOAN],
  setupLoginType: EntitySetupLoginType.AUTOMATED,
  sessionCategory: EntitySessionCategory.UNDEFINED,
  credentialsTemplate: {
    user: CredentialType.USER,
    password: CredentialType.PASSWORD,
  },
  iconUrl: null,
}

const createCryptoEntity = (
  num: number,
  name: string,
  features: Feature[] = [Feature.POSITION],
  requiredExternalIntegrations: ExternalIntegrationId[] = [],
): NativeCryptoWalletEntity => ({
  id: `c0000000-0000-0000-0000-000000000${String(num).padStart(3, "0")}`,
  name,
  naturalId: null,
  type: EntityType.CRYPTO_WALLET,
  origin: EntityOrigin.NATIVE,
  features,
  requiredExternalIntegrations,
  iconUrl: null,
})

export const BITCOIN = createCryptoEntity(1, "Bitcoin")
export const ETHEREUM = createCryptoEntity(2, "Ethereum")
export const LITECOIN = createCryptoEntity(3, "Litecoin")
export const TRON = createCryptoEntity(4, "Tron")
export const BSC = createCryptoEntity(5, "Binance Smart Chain")

export const COMMODITIES: Entity = {
  id: "ccccdddd-0000-0000-0000-000000000000",
  name: "Commodity Source",
  naturalId: null,
  type: EntityType.COMMODITY,
  origin: EntityOrigin.INTERNAL,
  iconUrl: null,
}

export const NATIVE_ENTITIES: Array<Entity> = [
  MY_INVESTOR,
  UNICAJA,
  TRADE_REPUBLIC,
  URBANITAE,
  WECITY,
  SEGO,
  MINTOS,
  F24,
  INDEXA_CAPITAL,
  ING,
  CAJAMAR,
  BITCOIN,
  ETHEREUM,
  LITECOIN,
  TRON,
  BSC,
  COMMODITIES,
]

export function getNativeById(
  entityId: string,
  ...entityTypes: EntityType[]
): Entity | undefined {
  return NATIVE_ENTITIES.find(
    e =>
      e.id === entityId &&
      (entityTypes.length === 0 || entityTypes.includes(e.type as EntityType)),
  )
}
