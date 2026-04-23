import { appConsole } from "@/lib/capacitor/appConsole"

const YF_BASE = "https://query2.finance.yahoo.com"
const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

let _crumb: string | null = null

async function ensureCrumb(): Promise<string> {
  if (_crumb) return _crumb

  try {
    await fetch("https://fc.yahoo.com", {
      headers: { "User-Agent": USER_AGENT },
      credentials: "include",
      redirect: "follow",
    })
  } catch {
    // Expected to fail — we only need the cookies it sets
  }

  const res = await fetch(`${YF_BASE}/v1/test/getcrumb`, {
    headers: { "User-Agent": USER_AGENT },
    credentials: "include",
  })

  if (!res.ok) throw new Error(`Crumb request failed: ${res.status}`)
  _crumb = await res.text()
  return _crumb
}

function resetCrumb() {
  _crumb = null
}

async function yfSearch(
  query: string,
  quotesCount = 15,
): Promise<{ quotes: any[] }> {
  const params = new URLSearchParams({
    q: query,
    quotesCount: String(quotesCount),
    newsCount: "0",
    enableFuzzyQuery: "false",
    quotesQueryId: "tss_match_phrase_query",
  })

  const res = await fetch(`${YF_BASE}/v1/finance/search?${params}`, {
    headers: { "User-Agent": USER_AGENT },
  })

  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

async function yfQuote(symbols: string[]): Promise<any[]> {
  const crumb = await ensureCrumb()
  const params = new URLSearchParams({
    symbols: symbols.join(","),
    crumb,
  })

  const res = await fetch(`${YF_BASE}/v7/finance/quote?${params}`, {
    headers: { "User-Agent": USER_AGENT },
    credentials: "include",
  })

  if (!res.ok) {
    if (res.status === 401) {
      resetCrumb()
      throw new Error("Crumb expired, retry needed")
    }
    throw new Error(`Quote failed: ${res.status}`)
  }

  const data = await res.json()
  return data.quoteResponse?.result ?? []
}

async function yfQuoteSummary(symbol: string, modules: string[]): Promise<any> {
  const crumb = await ensureCrumb()
  const params = new URLSearchParams({
    modules: modules.join(","),
    crumb,
  })

  const res = await fetch(
    `${YF_BASE}/v10/finance/quoteSummary/${encodeURIComponent(symbol)}?${params}`,
    {
      headers: { "User-Agent": USER_AGENT },
      credentials: "include",
    },
  )

  if (!res.ok) {
    if (res.status === 401) {
      resetCrumb()
      throw new Error("Crumb expired, retry needed")
    }
    throw new Error(`QuoteSummary failed: ${res.status}`)
  }

  const data = await res.json()
  const result = data.quoteSummary?.result?.[0]
  if (!result) throw new Error(`No quoteSummary data for ${symbol}`)
  return result
}

function mapQuoteType(
  instrumentType: string,
): "EQUITY" | "ETF" | "MUTUALFUND" | undefined {
  switch (instrumentType) {
    case "STOCK":
      return "EQUITY"
    case "ETF":
      return "ETF"
    case "MUTUAL_FUND":
      return "MUTUALFUND"
    default:
      return undefined
  }
}

function reverseMapQuoteType(
  quoteType: string | undefined,
): string | undefined {
  if (!quoteType) return undefined
  switch (quoteType.toUpperCase()) {
    case "EQUITY":
      return "STOCK"
    case "ETF":
      return "ETF"
    case "MUTUALFUND":
    case "FUND":
      return "MUTUAL_FUND"
    default:
      return undefined
  }
}

async function lookup(query: string, instrumentType: string): Promise<string> {
  try {
    const searchResult = await yfSearch(query, 15)
    const targetQuoteType = mapQuoteType(instrumentType)

    const filtered = (searchResult.quotes ?? []).filter((q: any) => {
      if (!q.symbol) return false
      if (!targetQuoteType) return true
      if (targetQuoteType === "MUTUALFUND") return true
      return q.quoteType === targetQuoteType
    })

    const results = filtered.map((q: any) => ({
      symbol: String(q.symbol),
      name: String(q.longname || q.shortname || q.symbol),
      exchange: String(q.exchDisp || q.exchange || "") || null,
      quoteType: reverseMapQuoteType(q.quoteType),
    }))

    const enriched = await enrichWithQuotes(results)
    return JSON.stringify(enriched)
  } catch (error) {
    appConsole.error("[YahooFinanceBridge] lookup failed", error)
    return JSON.stringify([])
  }
}

async function enrichWithQuotes(
  results: Array<{
    symbol: string
    name: string
    exchange: string | null
    quoteType: string | undefined
  }>,
): Promise<
  Array<{
    symbol: string
    name: string
    exchange: string | null
    quoteType: string | undefined
    currency: string | null
    price: number | null
  }>
> {
  if (results.length === 0) return []

  try {
    const symbols = results.map(r => r.symbol)
    const quotes = await yfQuote(symbols)
    const quoteMap = new Map<string, any>()
    for (const q of quotes) {
      quoteMap.set(q.symbol, q)
    }

    return results.map(r => {
      const q = quoteMap.get(r.symbol)
      return {
        ...r,
        currency: q?.currency ?? null,
        price: q?.regularMarketPrice ?? null,
      }
    })
  } catch (error) {
    appConsole.warn("[YahooFinanceBridge] quote enrichment failed", error)
    return results.map(r => ({ ...r, currency: null, price: null }))
  }
}

async function getInstrumentInfo(
  query: string,
  instrumentType: string,
): Promise<string> {
  try {
    const symbol = await resolveSymbol(query, instrumentType)
    if (!symbol) return JSON.stringify(null)

    const summary = await yfQuoteSummary(symbol, [
      "price",
      "quoteType",
      "summaryDetail",
    ])

    const price = summary.price
    if (!price) return JSON.stringify(null)

    const marketPrice =
      price.regularMarketPrice?.raw ?? price.regularMarketPrice
    const currency = price.currency
    const name = price.longName || price.shortName || symbol

    if (marketPrice === undefined || !currency) {
      return JSON.stringify(null)
    }

    const resolvedType =
      reverseMapQuoteType(price.quoteType) ||
      reverseMapQuoteType(summary.quoteType?.quoteType) ||
      instrumentType

    return JSON.stringify({
      name,
      currency,
      type: resolvedType,
      price: marketPrice,
      symbol,
    })
  } catch (error) {
    appConsole.error("[YahooFinanceBridge] getInstrumentInfo failed", error)
    return JSON.stringify(null)
  }
}

async function resolveSymbol(
  query: string,
  instrumentType: string,
): Promise<string | null> {
  if (!query) return null

  try {
    const searchResult = await yfSearch(query, 5)
    const targetQuoteType = mapQuoteType(instrumentType)

    for (const q of searchResult.quotes ?? []) {
      if (!q.symbol) continue
      if (!targetQuoteType) return String(q.symbol)
      if (q.quoteType === targetQuoteType) return String(q.symbol)
    }

    return query
  } catch {
    return query
  }
}

export const yahooFinanceBridge = {
  lookup,
  getInstrumentInfo,
}
