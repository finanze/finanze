import { EntitiesPosition } from "./globalPosition"
import { Dezimal } from "@/domain/dezimal"

export interface ForecastRequest {
  targetDate: string
  avgAnnualMarketIncrease?: Dezimal | null
  avgAnnualCryptoIncrease?: Dezimal | null
  avgAnnualCommodityIncrease?: Dezimal | null
}

export interface CashDelta {
  currency: string
  amount: Dezimal
}

export interface RealEstateEquityForecast {
  id: string
  equityNow: Dezimal | null
  equityAtTarget: Dezimal | null
  principalOutstandingNow: Dezimal | null
  principalOutstandingAtTarget: Dezimal | null
  currency: string
}

export interface ForecastResult {
  targetDate: string
  positions: EntitiesPosition
  cashDelta: CashDelta[]
  realEstate: RealEstateEquityForecast[]
  cryptoAppreciation: Dezimal
  commodityAppreciation: Dezimal
}
