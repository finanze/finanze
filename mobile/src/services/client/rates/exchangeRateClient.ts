import { ExchangeRateProvider } from "@/application/ports"
import { Dezimal } from "@/domain/dezimal"
import { ExchangeRates } from "@/domain"
import { httpGetJson } from "@/services/client/http/httpClient"

const AVAILABLE_CURRENCIES = ["EUR", "USD"]

const parseRates = (
  rates: Record<string, unknown>,
): Record<string, Dezimal> => {
  const parsed: Record<string, Dezimal> = {}
  for (const [currency, rate] of Object.entries(rates)) {
    parsed[currency.toUpperCase()] = Dezimal.fromString(String(rate))
  }
  return parsed
}

export class ExchangeRateClient implements ExchangeRateProvider {
  static readonly MATRIX_CACHE_TTL_MS = 2 * 60 * 60 * 1000
  static readonly TIMEOUT = 10

  static readonly BASE_URL =
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1"
  static readonly CURRENCIES_URL = `${ExchangeRateClient.BASE_URL}/currencies.min.json`

  private rates: ExchangeRates = {}
  private availableCurrencies: Record<string, string> = {}
  private updateDate: Date | null = null

  private matrixCacheExpiresAt: number | null = null
  private matrixLoadPromise: Promise<void> | null = null

  constructor() {
    // Mirror backend behavior: eagerly load once on init.
    this.matrixLoadPromise = this.loadRateMatrix(
      ExchangeRateClient.TIMEOUT,
    ).catch(e => {
      console.warn("Failed to load initial rate matrix", e)
    })
  }

  async getAvailableCurrencies(kwargs: any): Promise<Record<string, string>> {
    if (!Object.keys(this.availableCurrencies).length) {
      const timeout = kwargs?.timeout ?? ExchangeRateClient.TIMEOUT
      this.availableCurrencies = await this.fetchAvailableCurrencies(timeout)
    }
    return this.availableCurrencies
  }

  async getMatrix(kwargs: any): Promise<ExchangeRates> {
    const now = Date.now()

    if (this.matrixCacheExpiresAt !== null && now < this.matrixCacheExpiresAt) {
      return this.rates
    }

    if (!this.matrixLoadPromise) {
      const timeout = kwargs?.timeout ?? ExchangeRateClient.TIMEOUT

      // Mirror backend logic: reload when cache misses and date "changes".
      // Note: backend compares a date-string to a datetime, which is always != once initialized.
      const currentDate = this.getCurrentDate()
      if (currentDate !== (this.updateDate as any)) {
        this.matrixLoadPromise = this.loadRateMatrix(timeout)
      } else {
        this.matrixLoadPromise = this.loadRateMatrix(timeout)
      }
    }

    await this.matrixLoadPromise.finally(() => {
      this.matrixLoadPromise = null
    })

    this.matrixCacheExpiresAt =
      Date.now() + ExchangeRateClient.MATRIX_CACHE_TTL_MS
    return this.rates
  }

  private async fetchAvailableCurrencies(
    timeout: number,
  ): Promise<Record<string, string>> {
    const { response, data } = await httpGetJson<Record<string, string>>(
      ExchangeRateClient.CURRENCIES_URL,
      undefined,
      timeout,
    )

    if (!response.ok) {
      console.error("Error Response Body:" + JSON.stringify(data))
      throw new Error(
        `Failed to fetch available currencies: ${response.status}`,
      )
    }

    return data
  }

  private async fetchRates(currency: string, timeout: number): Promise<any> {
    const url = `${ExchangeRateClient.BASE_URL}/currencies/${currency.toLowerCase()}.min.json`
    const { response, data } = await httpGetJson<any>(url, undefined, timeout)

    if (!response.ok) {
      console.error("Error Response Body:" + JSON.stringify(data))
      throw new Error(
        `Failed to fetch rates for ${currency}: ${response.status}`,
      )
    }

    return data
  }

  private getCurrentDate(): string {
    const d = new Date()
    const yyyy = String(d.getFullYear())
    const mm = String(d.getMonth() + 1).padStart(2, "0")
    const dd = String(d.getDate()).padStart(2, "0")
    return `${yyyy}-${mm}-${dd}`
  }

  private async loadRateMatrix(timeout: number): Promise<void> {
    for (const currency of AVAILABLE_CURRENCIES) {
      const result = await this.fetchRates(currency, timeout)
      const dateStr = result?.date
      if (typeof dateStr === "string") {
        this.updateDate = new Date(dateStr)
      }
      const lower = currency.toLowerCase()
      const rawRates = result?.[lower] ?? {}
      this.rates[currency] = parseRates(rawRates)
    }
  }
}
