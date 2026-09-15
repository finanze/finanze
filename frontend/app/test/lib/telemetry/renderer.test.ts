import { beforeEach, describe, expect, it, vi } from "vitest"

import { PlatformType, type PlatformInfo } from "@/types"

const sendEvent = vi.fn().mockResolvedValue(true)
let platformInfo: PlatformInfo = { type: PlatformType.WEB }

vi.mock("@/env", () => ({
  BS_ENVIRONMENT: "test",
  BS_FRONTEND_DSN: "https://publickey@ingest.example.com/42",
}))

vi.mock("@/lib/telemetry/sentryEnvelope", async () => {
  const actual = await vi.importActual<
    typeof import("@/lib/telemetry/sentryEnvelope")
  >("@/lib/telemetry/sentryEnvelope")
  return {
    ...actual,
    sendEvent,
  }
})

vi.mock("@/lib/platform", () => ({
  isNativeMobile: () => false,
  getPlatformInfo: () => platformInfo,
}))

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn(),
    set: vi.fn(),
  },
}))

async function setup(errorReporting: boolean) {
  vi.resetModules()
  sendEvent.mockClear()
  localStorage.clear()
  platformInfo = { type: PlatformType.WEB }

  const { saveConsent } = await import("@/lib/telemetry/consent")
  const consent = await saveConsent({ errorReporting })
  const { reportError, setTelemetryContext } =
    await import("@/lib/telemetry/renderer")
  return { consent, reportError, setTelemetryContext }
}

describe("renderer error reporter", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("does not send when consent is off", async () => {
    const { reportError } = await setup(false)

    reportError(new Error("boom"))

    expect(sendEvent).not.toHaveBeenCalled()
  })

  it("posts a javascript envelope when consent is on", async () => {
    const { consent, reportError } = await setup(true)

    reportError(new Error("TELEMETRY_TEST: boom"))

    expect(sendEvent).toHaveBeenCalledTimes(1)
    const [dsn, event] = sendEvent.mock.calls[0]
    expect(dsn).toBe("https://publickey@ingest.example.com/42")
    expect(event.platform).toBe("javascript")
    expect(event.environment).toBe("test")
    expect(event.release).toBe("test")
    expect(event.user).toEqual({ id: consent.installId })
    expect(event.tags).toEqual({
      component: "renderer",
      distribution: "web",
    })
    expect(event.exception.values[0].type).toBe("Error")
    expect(event.exception.values[0].value).toBe("TELEMETRY_TEST: boom")
  })

  it("includes the user and backend version once known", async () => {
    const { consent, reportError, setTelemetryContext } = await setup(true)

    setTelemetryContext({ userId: "hashed-user", backendVersion: "0.9.2" })
    reportError(new Error("boom"))

    const [, event] = sendEvent.mock.calls[0]
    expect(event.user).toEqual({
      id: consent.installId,
      user_id: "hashed-user",
    })
    expect(event.tags).toMatchObject({
      user_id: "hashed-user",
      backend_version: "0.9.2",
    })
  })

  it("reports the local operating system when it is known", async () => {
    const { reportError } = await setup(true)
    platformInfo = { type: PlatformType.MAC, osVersion: "15.3.1" }

    reportError(new Error("boom"))

    const [, event] = sendEvent.mock.calls[0]
    expect(event.tags).toMatchObject({
      platform_os: "MACOS",
      os_version: "15.3.1",
    })
    expect(event.contexts).toEqual({ os: { name: "macOS", version: "15.3.1" } })
  })

  it("falls back to the backend operating system on web", async () => {
    const { reportError, setTelemetryContext } = await setup(true)

    setTelemetryContext({ backendOs: "LINUX", backendOsVersion: "6.8.0" })
    reportError(new Error("boom"))

    const [, event] = sendEvent.mock.calls[0]
    expect(event.tags).toMatchObject({
      distribution: "web",
      platform_os: "LINUX",
      os_version: "6.8.0",
    })
    expect(event.contexts).toEqual({ os: { name: "Linux", version: "6.8.0" } })
  })

  it("reports the cause when the thrown error only has library frames", async () => {
    const { reportError } = await setup(true)

    const cause = new Error("cannot read length of undefined")
    cause.stack = [
      "Error: cannot read length of undefined",
      "    at FundsPage (https://app.example.com/assets/index-abc.js:5:120)",
    ].join("\n")

    const wrapper = new Error("Minified React error #520", { cause })
    wrapper.stack = [
      "Error: Minified React error #520",
      "    at nc (../../node_modules/react-dom/cjs/react-dom-client.production.js:6063:22)",
    ].join("\n")

    reportError(wrapper)

    const [, event] = sendEvent.mock.calls[0]
    const values = event.exception.values
    expect(values).toHaveLength(2)
    expect(values[0].value).toBe("Minified React error #520")
    expect(values[1].value).toBe("cannot read length of undefined")
    expect(values[1].stacktrace.frames[0]).toMatchObject({
      function: "FundsPage",
      filename: "https://app.example.com/assets/index-abc.js",
      in_app: true,
    })
  })

  it("drops repeats of the same error within the dedupe window", async () => {
    const { reportError } = await setup(true)

    const stack = "Error: boom\n    at load (https://app.example.com/a.js:1:2)"
    for (let i = 0; i < 3; i++) {
      const error = new Error("boom")
      error.stack = stack
      reportError(error)
    }

    expect(sendEvent).toHaveBeenCalledTimes(1)
  })

  it("serializes non-error rejection reasons", async () => {
    const { reportError } = await setup(true)

    reportError({ code: 500, detail: "nope" })

    const [, event] = sendEvent.mock.calls[0]
    expect(event.exception.values[0].value).toBe('{"code":500,"detail":"nope"}')
  })

  it("keeps line and column of v8 frames", async () => {
    const { reportError } = await setup(true)

    const error = new Error("boom")
    error.stack = [
      "Error: boom",
      "    at load (https://app.example.com/assets/index-abc.js:1:4821)",
      "    at https://app.example.com/assets/vendor-def.js:12:99",
    ].join("\n")

    reportError(error)

    const [, event] = sendEvent.mock.calls[0]
    expect(event.exception.values[0].stacktrace.frames).toEqual([
      {
        function: undefined,
        filename: "https://app.example.com/assets/vendor-def.js",
        abs_path: "https://app.example.com/assets/vendor-def.js",
        lineno: 12,
        colno: 99,
        in_app: true,
      },
      {
        function: "load",
        filename: "https://app.example.com/assets/index-abc.js",
        abs_path: "https://app.example.com/assets/index-abc.js",
        lineno: 1,
        colno: 4821,
        in_app: true,
      },
    ])
  })

  it("parses webkit frames used on ios", async () => {
    const { reportError } = await setup(true)

    const error = new Error("boom")
    error.stack = "load@capacitor://localhost/assets/index-abc.js:1:4821"

    reportError(error)

    const [, event] = sendEvent.mock.calls[0]
    expect(event.exception.values[0].stacktrace.frames).toEqual([
      {
        function: "load",
        filename: "capacitor://localhost/assets/index-abc.js",
        abs_path: "capacitor://localhost/assets/index-abc.js",
        lineno: 1,
        colno: 4821,
        in_app: true,
      },
    ])
  })

  it("attaches debug images for chunks with a debug id", async () => {
    const { reportError } = await setup(true)

    const chunk = "https://app.example.com/assets/index-abc.js"
    ;(
      window as Window & { _sentryDebugIds?: Record<string, string> }
    )._sentryDebugIds = {
      [`Error\n    at ${chunk}:1:10`]: "11111111-2222-3333-4444-555555555555",
      [`Error\n    at https://app.example.com/assets/other.js:1:10`]:
        "99999999-9999-9999-9999-999999999999",
    }

    const error = new Error("boom")
    error.stack = `Error: boom\n    at load (${chunk}:1:4821)`

    reportError(error)

    const [, event] = sendEvent.mock.calls[0]
    expect(event.debug_meta).toEqual({
      images: [
        {
          type: "sourcemap",
          code_file: chunk,
          debug_id: "11111111-2222-3333-4444-555555555555",
        },
      ],
    })
  })
})
