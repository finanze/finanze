export type FilterValues = string | string[]

export interface SheetsGlobalConfig {
  spreadsheetId: string
  datetimeFormat?: string | null
  dateFormat?: string | null
}

export interface FilterConfig {
  field: string
  values: FilterValues
}

export interface BaseSheetConfig {
  range: string
  spreadsheetId?: string | null
  datetimeFormat?: string | null
  dateFormat?: string | null
  lastUpdate?: boolean | null
}

export interface TemplateConfig {
  id: string
  params?: Record<string, any> | null
}

export interface ExportSheetConfig extends BaseSheetConfig {
  data?: string[]
  filters?: FilterConfig[] | null
  template?: TemplateConfig | null
}

export interface ExportPositionSheetConfig extends ExportSheetConfig {}

export interface ExportContributionSheetConfig extends ExportSheetConfig {}

export interface ExportTransactionsSheetConfig extends ExportSheetConfig {}

export interface ExportHistoricSheetConfig extends ExportSheetConfig {}

export interface SheetsExportConfig {
  globals?: SheetsGlobalConfig | null
  position?: ExportPositionSheetConfig[]
  contributions?: ExportContributionSheetConfig[]
  transactions?: ExportTransactionsSheetConfig[]
  historic?: ExportHistoricSheetConfig[]
}

export interface ExportConfig {
  sheets?: SheetsExportConfig | null
}

export interface ImportSheetConfig extends BaseSheetConfig {
  template?: TemplateConfig | null
  data?: string
}

export interface ImportPositionSheetConfig extends ImportSheetConfig {}

export interface ImportTransactionsSheetConfig extends ImportSheetConfig {}

export interface SheetsImportConfig {
  globals?: SheetsGlobalConfig | null
  position?: ImportPositionSheetConfig[] | null
  transactions?: ImportTransactionsSheetConfig[] | null
}

export interface ImportConfig {
  sheets?: SheetsImportConfig | null
}

export interface CryptoAssetConfig {
  stablecoins?: string[]
  hideUnknownTokens?: boolean
}

export interface AssetConfig {
  crypto: CryptoAssetConfig
}

export interface GeneralConfig {
  defaultCurrency?: string
  defaultCommodityWeightUnit?: string
}

export enum AutoRefreshMode {
  OFF = "OFF",
  NO_2FA = "NO_2FA",
}

export enum AutoRefreshMaxOutdatedTime {
  THREE_HOURS = "THREE_HOURS",
  SIX_HOURS = "SIX_HOURS",
  TWELVE_HOURS = "TWELVE_HOURS",
  DAY = "DAY",
  TWO_DAYS = "TWO_DAYS",
  WEEK = "WEEK",
}

export interface AutoRefreshEntityEntry {
  id: string
}

export interface AutoRefresh {
  mode?: AutoRefreshMode
  maxOutdated?: AutoRefreshMaxOutdatedTime
  entities?: AutoRefreshEntityEntry[]
}

export interface DataConfig {
  autoRefresh?: AutoRefresh
}

export interface Settings {
  lastUpdate: string
  version?: number
  general?: GeneralConfig
  data?: DataConfig
  export?: ExportConfig
  importing?: ImportConfig
  assets?: AssetConfig
}
