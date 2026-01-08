export enum Feature {
  POSITION = "POSITION",
  AUTO_CONTRIBUTIONS = "AUTO_CONTRIBUTIONS",
  TRANSACTIONS = "TRANSACTIONS",
  HISTORIC = "HISTORIC",
}

export enum EntityType {
  FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION",
  CRYPTO_WALLET = "CRYPTO_WALLET",
  CRYPTO_EXCHANGE = "CRYPTO_EXCHANGE",
  COMMODITY = "COMMODITY",
}

export enum EntityOrigin {
  MANUAL = "MANUAL",
  NATIVE = "NATIVE",
  EXTERNALLY_PROVIDED = "EXTERNALLY_PROVIDED",
  INTERNAL = "INTERNAL",
}

export interface Entity {
  id: string | null
  name: string
  naturalId: string | null
  type: EntityType
  origin: EntityOrigin
  iconUrl: string | null
}
