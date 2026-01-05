import { fetchWithTimeout, QueryParams } from "./httpClient"

export type BackoffOptions = {
  url: string
  params?: QueryParams
  timeoutSec?: number
  headers?: Record<string, string>
  maxRetries?: number
  backoffExponentBase?: number
  backoffFactor?: number
  retriedStatuses?: number[]
  cooldownSec?: number
  shouldRetry?: (resp: Response, attempt: number) => boolean
}

const DEFAULT_RETRIED_STATUSES = [429, 408]

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const jitter = (max: number): number => Math.random() * max

export const httpGetWithBackoff = async (
  opts: BackoffOptions,
): Promise<Response> => {
  const {
    url,
    params,
    timeoutSec = 10,
    headers,
    maxRetries = 3,
    backoffExponentBase = 2.0,
    backoffFactor = 0.5,
    retriedStatuses = DEFAULT_RETRIED_STATUSES,
    cooldownSec,
    shouldRetry,
  } = opts

  const retried = new Set(retriedStatuses)

  let attempt = 0
  let lastError: unknown = null

  // attempt <= maxRetries => maxRetries+1 total tries (matches backend)
  while (attempt <= maxRetries) {
    if (cooldownSec) {
      await sleep(cooldownSec * 1000)
    }

    let response: Response
    try {
      const requestUrl = (() => {
        if (!params) return url
        const u = new URL(url)
        for (const [k, v] of Object.entries(params)) {
          if (v === null || v === undefined) continue
          u.searchParams.set(k, String(v))
        }
        return u.toString()
      })()

      response = await fetchWithTimeout(requestUrl, {
        method: "GET",
        headers,
        timeoutSec,
      })
    } catch (e) {
      lastError = e
      if (attempt === maxRetries) throw e

      const delaySec =
        backoffFactor * Math.pow(backoffExponentBase, attempt) +
        jitter(backoffFactor)
      await sleep(delaySec * 1000)
      attempt += 1
      continue
    }

    if (retried.has(response.status) && !response.ok) {
      if (attempt === maxRetries) return response

      const delaySec =
        backoffFactor * Math.pow(backoffExponentBase, attempt) +
        jitter(backoffFactor)
      await sleep(delaySec * 1000)
      attempt += 1
      continue
    }

    if (shouldRetry && shouldRetry(response, attempt) && attempt < maxRetries) {
      const delaySec =
        backoffFactor * Math.pow(backoffExponentBase, attempt) +
        jitter(backoffFactor)
      await sleep(delaySec * 1000)
      attempt += 1
      continue
    }

    return response
  }

  if (lastError) throw lastError
  throw new Error("httpGetWithBackoff reached an unexpected state")
}
