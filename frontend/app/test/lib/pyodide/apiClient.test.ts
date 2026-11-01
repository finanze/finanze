import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  callPythonFunction: vi.fn(),
}))

vi.mock("@/lib/pyodide", () => ({
  callPythonFunction: mocks.callPythonFunction,
}))

vi.mock("@/lib/pyodide/init", () => ({
  ensureInitialized: vi.fn().mockResolvedValue(undefined),
  withApiPrefix: (path: string) => `/api/v1${path}`,
}))

vi.mock("@/lib/pyodide/bridge", () => ({ jsBridge: {} }))

vi.mock("@/lib/capacitor/appConsole", () => ({
  appConsole: { debug: vi.fn(), warn: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

import { PyodideApiClient } from "@/lib/pyodide/apiClient"

describe("PyodideApiClient", () => {
  beforeEach(() => {
    mocks.callPythonFunction.mockReset()
  })

  it("parses JSON text responses keeping null values", async () => {
    mocks.callPythonFunction.mockResolvedValue({
      status: 200,
      json: '{"label_id":null,"comparison":{"actual":null,"expected":300.0}}',
      headers: { "Content-Type": "application/json" },
    })

    const result = await new PyodideApiClient().get<any>("/cashflow/summary")

    expect(result).toEqual({
      label_id: null,
      comparison: { actual: null, expected: 300 },
    })
    expect(result.label_id).toBeNull()
  })

  it("exposes error fields from JSON text responses", async () => {
    mocks.callPythonFunction.mockResolvedValue({
      status: 409,
      json: '{"code":"REQUIRED_INTEGRATION","message":"Missing","details":{"required":["X"]}}',
      headers: {},
    })

    await expect(
      new PyodideApiClient().post("/fetch", {}),
    ).rejects.toMatchObject({
      message: "Missing",
      status: 409,
      code: "REQUIRED_INTEGRATION",
      details: { required: ["X"] },
    })
  })

  it("keeps raw data responses", async () => {
    mocks.callPythonFunction.mockResolvedValue({
      status: 200,
      data: { legacy: true },
      headers: {},
    })

    await expect(new PyodideApiClient().get("/legacy")).resolves.toEqual({
      legacy: true,
    })
  })

  it("downloads binary and JSON text responses", async () => {
    const client = new PyodideApiClient()
    mocks.callPythonFunction.mockResolvedValueOnce({
      status: 200,
      data: new Uint8Array([1, 2, 3]),
      headers: { "Content-Type": "image/png" },
    })
    mocks.callPythonFunction.mockResolvedValueOnce({
      status: 200,
      json: '{"value":null}',
      headers: { "Content-Type": "application/json" },
    })

    const binary = await client.download("/image")
    const json = await client.download("/export")

    expect(binary.contentType).toBe("image/png")
    expect(binary.blob.size).toBe(3)
    expect(await json.blob.text()).toBe('{"value":null}')
  })
})
