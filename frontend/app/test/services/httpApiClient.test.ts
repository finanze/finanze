import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/env", () => ({ BASE_URL: "http://backend.test" }))

const SESSION_KEY = "finanze_api_session"

const fakeResponse = (status = 204, body = "") => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: "",
  text: async () => body,
  json: async () => (body ? JSON.parse(body) : {}),
  blob: async () => new Blob([body]),
  headers: new Headers(),
})

const fetchMock = vi.fn()

const loadClient = async () => {
  vi.resetModules()
  const { HttpApiClient } = await import("@/services/httpApiClient")
  return new HttpApiClient()
}

const lastHeaders = (): Record<string, string> =>
  (fetchMock.mock.calls.at(-1)?.[1]?.headers ?? {}) as Record<string, string>

beforeEach(() => {
  window.sessionStorage.clear()
  fetchMock.mockReset()
  fetchMock.mockImplementation(async () => fakeResponse())
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("HttpApiClient session token", () => {
  it("sends no Authorization header without a session", async () => {
    const client = await loadClient()

    await client.get("/settings")

    expect(lastHeaders().Authorization).toBeUndefined()
  })

  it("attaches the bearer token to requests and downloads", async () => {
    const client = await loadClient()
    client.setSessionToken("abc")

    await client.post("/settings", { a: 1 })
    expect(lastHeaders().Authorization).toBe("Bearer abc")

    await client.download("/export/file", { a: 1 })
    expect(lastHeaders().Authorization).toBe("Bearer abc")
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe("abc")
  })

  it("restores the token from sessionStorage after a reload", async () => {
    window.sessionStorage.setItem(SESSION_KEY, "persisted")
    const client = await loadClient()

    await client.get("/positions")

    expect(lastHeaders().Authorization).toBe("Bearer persisted")
  })

  it("keeps an explicit Authorization header", async () => {
    const client = await loadClient()
    client.setSessionToken("abc")

    await client.get("/positions", { headers: { Authorization: "Custom x" } })

    expect(lastHeaders().Authorization).toBe("Custom x")
  })

  it("clears the token on reset and when the server URL is refreshed", async () => {
    const client = await loadClient()
    client.setSessionToken("abc")
    client.setSessionToken(null)
    await client.get("/positions")
    expect(lastHeaders().Authorization).toBeUndefined()
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()

    client.setSessionToken("def")
    await client.refreshApiBaseUrl()
    await client.get("/positions")
    expect(lastHeaders().Authorization).toBeUndefined()
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })
})
