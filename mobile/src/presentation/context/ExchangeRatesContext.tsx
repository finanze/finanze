import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { Dezimal } from "@/domain"
import type { ExchangeRates } from "@/domain"
import { useApplicationContainer } from "./ApplicationContainerContext"

interface ExchangeRatesContextType {
  exchangeRates: ExchangeRates
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const ExchangeRatesContext = createContext<
  ExchangeRatesContextType | undefined
>(undefined)

const DEFAULT_EXCHANGE_RATES: ExchangeRates = {
  EUR: { EUR: Dezimal.fromString("1"), USD: Dezimal.fromString("1") },
  USD: { USD: Dezimal.fromString("1"), EUR: Dezimal.fromString("1") },
}

export function ExchangeRatesProvider({ children }: { children: ReactNode }) {
  const container = useApplicationContainer()

  const [exchangeRates, setExchangeRates] = useState<ExchangeRates>(
    DEFAULT_EXCHANGE_RATES,
  )
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const initialLoadRef = useRef(true)
  const inFlightRef = useRef<Promise<void> | null>(null)

  const refresh = useCallback(async () => {
    if (inFlightRef.current) {
      return inFlightRef.current
    }

    const run = (async () => {
      try {
        setIsLoading(true)
        setError(null)

        const data = await container.getExchangeRates.execute(
          initialLoadRef.current,
        )
        initialLoadRef.current = false

        setExchangeRates(prev => {
          return data && Object.keys(data).length ? data : prev
        })
      } catch (e: any) {
        // Never block the app for background refresh failures.
        setError(
          e?.message ? String(e.message) : "Failed to load exchange rates",
        )
      } finally {
        setIsLoading(false)
        inFlightRef.current = null
      }
    })()

    inFlightRef.current = run
    return run
  }, [container])

  useEffect(() => {
    // Warm up rates in the background on app start.
    void refresh()
  }, [refresh])

  const value = useMemo(
    () => ({
      exchangeRates,
      isLoading,
      error,
      refresh,
    }),
    [exchangeRates, isLoading, error, refresh],
  )

  return (
    <ExchangeRatesContext.Provider value={value}>
      {children}
    </ExchangeRatesContext.Provider>
  )
}

export function useExchangeRates(): ExchangeRatesContextType {
  const ctx = useContext(ExchangeRatesContext)
  if (!ctx) {
    throw new Error(
      "useExchangeRates must be used within an ExchangeRatesProvider",
    )
  }
  return ctx
}
