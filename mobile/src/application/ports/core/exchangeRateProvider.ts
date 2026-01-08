import { ExchangeRates } from "@/domain"

export interface ExchangeRateProvider {
  getAvailableCurrencies(kwargs: any): Promise<Record<string, string>>
  getMatrix(kwargs: any): Promise<ExchangeRates>
}
