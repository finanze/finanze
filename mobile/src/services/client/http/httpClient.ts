export type QueryParams = Record<
  string,
  string | number | boolean | null | undefined
>

const buildUrl = (baseUrl: string, params?: QueryParams): string => {
  if (!params) return baseUrl

  const url = new URL(baseUrl)
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined) continue
    url.searchParams.set(k, String(v))
  }
  return url.toString()
}

export class HttpTimeoutError extends Error {
  constructor(message: string = "Request timed out") {
    super(message)
    this.name = "HttpTimeoutError"
  }
}

export const fetchWithTimeout = async (
  url: string,
  opts: RequestInit & { timeoutSec?: number } = {},
): Promise<Response> => {
  const timeoutSec = opts.timeoutSec
  if (!timeoutSec || timeoutSec <= 0) {
    const { timeoutSec: _timeoutSec, ...rest } = opts
    void _timeoutSec
    return fetch(url, rest)
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutSec * 1000)

  try {
    const { timeoutSec: _timeoutSec, ...rest } = opts
    void _timeoutSec
    return await fetch(url, { ...rest, signal: controller.signal })
  } catch (e: any) {
    if (e?.name === "AbortError") {
      throw new HttpTimeoutError()
    }
    throw e
  } finally {
    clearTimeout(timeoutId)
  }
}

export const httpGetJson = async <T>(
  baseUrl: string,
  params?: QueryParams,
  timeoutSec?: number,
  headers?: Record<string, string>,
): Promise<{ response: Response; data: T }> => {
  const url = buildUrl(baseUrl, params)
  const response = await fetchWithTimeout(url, {
    method: "GET",
    timeoutSec,
    headers,
  })

  let data: T
  try {
    data = (await response.json()) as T
  } catch {
    const text = await response.text().catch(() => "")
    throw new Error(`Failed to decode JSON from ${url}: ${text.slice(0, 200)}`)
  }

  return { response, data }
}

export const httpGetText = async (
  baseUrl: string,
  params?: QueryParams,
  timeoutSec?: number,
  headers?: Record<string, string>,
): Promise<{ response: Response; data: string }> => {
  const url = buildUrl(baseUrl, params)
  const response = await fetchWithTimeout(url, {
    method: "GET",
    timeoutSec,
    headers,
  })
  const data = await response.text()
  return { response, data }
}
