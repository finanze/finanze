import { Dezimal } from "@/domain/dezimal"

export enum InstrumentType {
  STOCK = "STOCK",
  ETF = "ETF",
  MUTUAL_FUND = "MUTUAL_FUND",
}

export interface InstrumentDataRequest {
  type: InstrumentType
  isin?: string | null
  name?: string | null
  ticker?: string | null
}

export interface InstrumentOverview {
  isin?: string | null
  name?: string | null
  currency?: string | null
  symbol?: string | null
  type?: InstrumentType | null
  market?: string | null
  price?: Dezimal | null
}

export interface InstrumentInfo {
  name: string
  currency: string
  type: InstrumentType
  price: Dezimal
  symbol?: string | null
}
