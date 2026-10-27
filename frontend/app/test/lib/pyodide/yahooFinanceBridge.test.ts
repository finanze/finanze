import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/capacitor/appConsole", () => ({
  appConsole: { warn: vi.fn(), error: vi.fn() },
}))

import { yahooFinanceBridge } from "@/lib/pyodide/bridges/yahooFinanceBridge"

describe("yahooFinanceBridge.getSplits", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it.each([
    { numerator: 2, denominator: 1, ratio: 2 },
    { numerator: 1, denominator: 5, ratio: 0.2 },
  ])("returns forward and reverse split ratios", async split => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        chart: {
          result: [
            {
              timestamp: [],
              events: {
                splits: {
                  "1748822400": { date: 1748822400, ...split },
                },
              },
            },
          ],
        },
      }),
    })

    const result = await yahooFinanceBridge.getSplits(
      "TEST",
      "2025-01-01",
      "2025-12-31",
    )

    expect(JSON.parse(result)).toEqual([
      { date: "2025-06-02", ratio: split.ratio },
    ])
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("returns an empty list when the provider reports no splits", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ chart: { result: [{ timestamp: [] }] } }),
    })

    const result = await yahooFinanceBridge.getSplits(
      "TEST",
      "2025-01-01",
      "2025-12-31",
    )

    expect(JSON.parse(result)).toEqual([])
  })

  it("distinguishes a network failure from a successful empty result", async () => {
    fetchMock.mockRejectedValue(new Error("Offline"))

    const result = await yahooFinanceBridge
      .getSplits("TEST", "2025-01-01", "2025-12-31")
      .then(
        raw => JSON.parse(raw),
        () => null,
      )

    expect(result).toBeNull()
  })

  it("distinguishes an HTTP failure from a successful empty result", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503 })

    const result = await yahooFinanceBridge
      .getSplits("TEST", "2025-01-01", "2025-12-31")
      .then(
        raw => JSON.parse(raw),
        () => null,
      )

    expect(result).toBeNull()
  })

  it("distinguishes a provider error response from an empty result", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        chart: { result: null, error: { code: "Unavailable" } },
      }),
    })

    const result = await yahooFinanceBridge.getSplits(
      "TEST",
      "2025-01-01",
      "2025-12-31",
    )

    expect(JSON.parse(result)).toBeNull()
  })
})
