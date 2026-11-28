export interface AccountExclusion {
  type: "IBAN"
  value: string
}

export interface AccountAssetConfig {
  exclusions: AccountExclusion[]
}
