import { ExchangeRates } from "@/domain"

export interface ExchangeRateStorage {
  get(): Promise<ExchangeRates>
  save(exchangeRates: ExchangeRates): Promise<void>
  getLastSaved(): Promise<string | null>
}
