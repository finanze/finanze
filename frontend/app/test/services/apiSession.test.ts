import { beforeEach, describe, expect, it, vi } from "vitest"
import { login, logout, signup } from "@/services/api"
import { AuthResultCode } from "@/types"

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
  setSessionToken: vi.fn(),
}))
vi.mock("@/services/apiClient", () => ({
  getApiClient: async () => ({
    post: mocks.post,
    setSessionToken: mocks.setSessionToken,
  }),
}))
vi.mock("@/lib/mobile", () => ({
  triggerDeferredInit: vi.fn(),
  isBackgroundUpdateAvailable: vi.fn(),
  backgroundUpdateQuotes: vi.fn(),
  backgroundUpdateLoans: vi.fn(),
  backgroundGetNetworthTimeline: vi.fn(),
  backgroundGetGainsTimeline: vi.fn(),
}))

const credentials = { username: "alice", password: "secret123" }

beforeEach(() => {
  mocks.post.mockReset()
  mocks.setSessionToken.mockReset()
  vi.spyOn(console, "error").mockImplementation(() => {})
})

describe("API session token lifecycle", () => {
  it("stores the token returned by login", async () => {
    mocks.post.mockResolvedValue({ token: "tok" })

    expect(await login(credentials)).toEqual({ code: AuthResultCode.SUCCESS })
    expect(mocks.setSessionToken).toHaveBeenCalledWith("tok", undefined)
  })

  it("forwards the remember flag to the server and token storage", async () => {
    mocks.post.mockResolvedValue({ token: "tok" })

    await login({ ...credentials, remember: true })

    expect(mocks.post).toHaveBeenCalledWith("/login", {
      ...credentials,
      remember: true,
    })
    expect(mocks.setSessionToken).toHaveBeenCalledWith("tok", true)
  })

  it("keeps working with servers that answer without a token", async () => {
    mocks.post.mockResolvedValue(null)

    expect(await login(credentials)).toEqual({ code: AuthResultCode.SUCCESS })
    expect(mocks.setSessionToken).not.toHaveBeenCalled()
  })

  it("does not store anything on invalid credentials", async () => {
    mocks.post.mockRejectedValue(Object.assign(new Error("x"), { status: 401 }))

    expect(await login(credentials)).toEqual({
      code: AuthResultCode.INVALID_CREDENTIALS,
    })
    expect(mocks.setSessionToken).not.toHaveBeenCalled()
  })

  it("stores the token returned by signup", async () => {
    mocks.post.mockResolvedValue({ token: "signup-tok" })

    expect(await signup({ ...credentials, remember: true })).toEqual({
      success: true,
    })
    expect(mocks.setSessionToken).toHaveBeenCalledWith("signup-tok", true)
  })

  it("clears the token after logout", async () => {
    mocks.post.mockResolvedValue(null)

    await logout()

    expect(mocks.post).toHaveBeenCalledWith("/logout")
    expect(mocks.setSessionToken).toHaveBeenCalledWith(null)
  })
})
