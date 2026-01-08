import AsyncStorage from "@react-native-async-storage/async-storage"

import { ExchangeRateStorage } from "@/application/ports"
import { ExchangeRates } from "@/domain"
import { Dezimal } from "@/domain/dezimal"

const STORAGE_KEY = "finanze.exchangeRates.v1"

type StoredPayload = {
  last_saved?: string
  rates?: Record<string, Record<string, string>>
}

export class AsyncStorageExchangeRateStorage implements ExchangeRateStorage {
  private lastSaved: string | null = null
  private ratesCache: ExchangeRates = {}

  async get(): Promise<ExchangeRates> {
    // Ensure we loaded at least once (best-effort); if not, return current cache.
    if (this.lastSaved === null && Object.keys(this.ratesCache).length === 0) {
      await this.load()
    }
    return this.ratesCache
  }

  async save(exchangeRates: ExchangeRates): Promise<void> {
    const serializable: Record<string, Record<string, string>> = {}

    for (const [base, quotes] of Object.entries(exchangeRates ?? {})) {
      if (!quotes || typeof quotes !== "object") continue
      serializable[base] = {}
      for (const [quote, dez] of Object.entries(quotes)) {
        try {
          serializable[base][quote] = String(dez)
        } catch {
          // Keep behavior tolerant: skip invalid serializations.
        }
      }
    }

    const nowIso = new Date().toISOString()
    const payload: StoredPayload = {
      last_saved: nowIso,
      rates: serializable,
    }

    try {
      const encoded = JSON.stringify(payload)
      await AsyncStorage.setItem(STORAGE_KEY, encoded)

      // Best-effort verification readback (debug only).
      const verify = await AsyncStorage.getItem(STORAGE_KEY)

      this.lastSaved = nowIso
      this.ratesCache = exchangeRates
    } catch (e) {
      console.error("Failed to persist exchange rates:", e)
    }
  }

  async getLastSaved(): Promise<string | null> {
    if (this.lastSaved === null) {
      await this.load()
    }
    return this.lastSaved
  }

  private async load(): Promise<void> {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY)

      if (!raw) return
      if (!raw.trim()) return

      const data = JSON.parse(raw) as unknown
      if (!data || typeof data !== "object") return

      const obj = data as StoredPayload

      if (typeof obj.last_saved === "string") {
        // Validate timestamp shape similarly to backend.
        const d = new Date(obj.last_saved)
        if (Number.isFinite(d.getTime())) {
          this.lastSaved = obj.last_saved
        } else {
          console.warn(
            "Malformed last_saved timestamp in exchangeRates storage",
          )
        }
      }

      const rawRates = obj.rates ?? {}
      if (rawRates && typeof rawRates === "object") {
        const parsed: ExchangeRates = {}
        for (const [base, quotes] of Object.entries(rawRates)) {
          if (!quotes || typeof quotes !== "object") continue
          parsed[base] = {}
          for (const [quote, val] of Object.entries(quotes)) {
            try {
              parsed[base]![quote] = Dezimal.fromString(String(val))
            } catch {
              console.warn(
                `Skipping invalid rate ${base}->${quote} value=${String(val)}`,
              )
            }
          }
        }
        this.ratesCache = parsed
      }
    } catch (e) {
      console.warn("Failed to load exchange rates from storage:", e)
    }
  }
}
