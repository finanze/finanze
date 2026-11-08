import { beforeEach, describe, expect, it, vi } from "vitest"
import { fetchExternalEntity } from "@/services/api"
import { type Feature, FetchResultCode } from "@/types"

const mocks = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock("@/services/apiClient", () => ({
  getApiClient: async () => ({ post: mocks.post }),
}))
vi.mock("@/lib/mobile", () => ({
  triggerDeferredInit: vi.fn(),
  isBackgroundUpdateAvailable: vi.fn(),
  backgroundUpdateQuotes: vi.fn(),
  backgroundUpdateLoans: vi.fn(),
  backgroundGetNetworthTimeline: vi.fn(),
  backgroundGetGainsTimeline: vi.fn(),
}))

beforeEach(() => {
  mocks.post.mockReset()
})

describe("External fetch requests", () => {
  it("forwards selected features and deep mode without changing provider contracts", async () => {
    const response = { code: FetchResultCode.COMPLETED }
    mocks.post.mockResolvedValue(response)
    const options: { features: Feature[]; deep: boolean } = {
      features: ["TRANSACTIONS"],
      deep: true,
    }
    expect(await fetchExternalEntity("external-bank", options)).toEqual(
      response,
    )
    expect(mocks.post).toHaveBeenCalledWith(
      "/data/fetch/external/external-bank",
      options,
    )
  })

  it("preserves the existing no-body default request", async () => {
    await fetchExternalEntity("external-bank")
    expect(mocks.post).toHaveBeenCalledWith(
      "/data/fetch/external/external-bank",
      undefined,
    )
  })

  it("propagates cooldown and provider errors instead of returning success", async () => {
    const error = Object.assign(new Error("Cooldown"), {
      status: 429,
      code: "COOLDOWN",
    })
    mocks.post.mockRejectedValue(error)
    await expect(
      fetchExternalEntity("external-bank", { features: ["POSITION"] }),
    ).rejects.toEqual(error)
  })
})
