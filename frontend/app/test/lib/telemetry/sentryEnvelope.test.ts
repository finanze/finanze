import { afterEach, describe, expect, it, vi } from "vitest"

import { buildEvent, parseDsn, sendEvent } from "@/lib/telemetry/sentryEnvelope"

const DSN = "https://publickey@ingest.example.com/42"

describe("parseDsn", () => {
  it("extracts host, project and key", () => {
    expect(parseDsn(DSN)).toEqual({
      host: "ingest.example.com",
      projectId: "42",
      publicKey: "publickey",
      protocol: "https",
    })
  })

  it("returns null for invalid dsn", () => {
    expect(parseDsn("not a dsn")).toBeNull()
    expect(parseDsn("https://ingest.example.com/42")).toBeNull()
  })
})

describe("buildEvent", () => {
  it("builds an exception event with the given context", () => {
    const event = buildEvent(
      {
        type: "ValueError",
        value: "boom",
        frames: [{ filename: "a.py", lineno: 3 }],
        tags: { component: "mobile-backend" },
      },
      {
        platform: "python",
        environment: "production",
        release: "1.2.3",
        installId: "install-1",
      },
    )

    expect(event.platform).toBe("python")
    expect(event.environment).toBe("production")
    expect(event.release).toBe("1.2.3")
    expect(event.user).toEqual({ id: "install-1" })
    expect(event.tags).toEqual({ component: "mobile-backend" })
    expect((event.exception as any).values[0].type).toBe("ValueError")
    expect((event.exception as any).values[0].stacktrace.frames).toHaveLength(1)
  })

  it("omits the stacktrace when there are no frames", () => {
    const event = buildEvent(
      { type: "Error", value: "x" },
      { platform: "javascript" },
    )

    expect((event.exception as any).values[0].stacktrace).toBeUndefined()
  })
})

describe("sendEvent", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("posts an envelope to the ingest endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal("fetch", fetchMock)

    const event = buildEvent(
      { type: "Error", value: "x" },
      { platform: "javascript" },
    )
    const result = await sendEvent(DSN, event)

    expect(result).toBe(true)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain("https://ingest.example.com/api/42/envelope/")
    expect(url).toContain("sentry_key=publickey")
    expect(init.body.split("\n")).toHaveLength(4)
  })

  it("does not throw when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))

    const event = buildEvent(
      { type: "Error", value: "x" },
      { platform: "javascript" },
    )

    await expect(sendEvent(DSN, event)).resolves.toBe(false)
  })

  it("does nothing with an invalid dsn", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const event = buildEvent(
      { type: "Error", value: "x" },
      { platform: "javascript" },
    )

    expect(await sendEvent("nope", event)).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
