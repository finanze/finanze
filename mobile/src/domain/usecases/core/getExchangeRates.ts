import { ExchangeRates } from "@/domain"

export interface GetExchangeRates {
  execute(initialLoad: boolean): Promise<ExchangeRates>
}
