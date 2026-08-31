import { app } from "electron"
import { homedir } from "node:os"
import { join } from "node:path"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { randomUUID } from "node:crypto"

const CONSENT_FILE = "telemetry.json"
const REDACTED = "[redacted]"
const MAX_FRAMES = 30

const EMAIL_RE = /[\w.+-]+@[\w-]+\.[\w.]+/g
const LONG_HEX_RE = /\b[0-9a-fA-F]{26,}\b/g
const IBAN_RE = /\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b/g

export interface TelemetryConsent {
  errorReporting: boolean
  sessionReplay: boolean
  installId: string
}

let consent: TelemetryConsent = {
  errorReporting: false,
  sessionReplay: false,
  installId: "",
}

let dsn = ""
let environment = "production"

function consentPath(): string {
  return join(app.getPath("userData"), CONSENT_FILE)
}

function readConsent(): TelemetryConsent {
  try {
    const raw = JSON.parse(readFileSync(consentPath(), "utf-8"))
    return {
      errorReporting: raw.error_reporting === true,
      sessionReplay: raw.session_replay === true,
      installId: typeof raw.install_id === "string" ? raw.install_id : "",
    }
  } catch {
    return { errorReporting: false, sessionReplay: false, installId: "" }
  }
}

function writeConsent(value: TelemetryConsent): void {
  const payload = {
    error_reporting: value.errorReporting,
    session_replay: value.sessionReplay,
    install_id: value.installId,
    updated_at: new Date().toISOString(),
  }

  try {
    mkdirSync(app.getPath("userData"), { recursive: true })
    writeFileSync(consentPath(), JSON.stringify(payload, null, 2), "utf-8")
  } catch (error) {
    console.error("Failed to persist telemetry consent:", error)
  }
}

function scrub(text: string): string {
  return text
    .split(homedir())
    .join("~")
    .replace(EMAIL_RE, REDACTED)
    .replace(IBAN_RE, REDACTED)
    .replace(LONG_HEX_RE, REDACTED)
    .slice(0, 2000)
}

interface Frame {
  filename: string
  function?: string
  lineno?: number
}

function parseStack(stack: string | undefined): Frame[] {
  if (!stack) return []

  const frames: Frame[] = []
  for (const line of stack.split("\n").slice(1)) {
    const match = line.trim().match(/^at\s+(?:(.+?)\s+\()?(.+?):(\d+):\d+\)?$/)
    if (!match) continue
    frames.push({
      function: match[1],
      filename: scrub(match[2]),
      lineno: Number(match[3]),
    })
  }

  return frames.slice(0, MAX_FRAMES).reverse()
}

function parseDsn(value: string) {
  try {
    const url = new URL(value)
    const projectId = url.pathname.replace(/^\//, "")
    if (!url.username || !projectId) return null
    return {
      endpoint:
        `${url.protocol}//${url.host}/api/${projectId}/envelope/` +
        `?sentry_key=${url.username}&sentry_version=7&sentry_client=finanze`,
    }
  } catch {
    return null
  }
}

export function isTelemetryEnabled(): boolean {
  return consent.errorReporting && !!dsn
}

export function getTelemetryConsent(): TelemetryConsent {
  return { ...consent }
}

export function getBackendTelemetryEnv(): Record<string, string> {
  if (!__BS_DESKTOP_BACKEND_DSN__) return {}

  // The DSN is always provided so the backend can be toggled at runtime; it
  // keeps reporting disabled until its own consent file says otherwise.
  return {
    FINANZE_ERRORS_DSN: __BS_DESKTOP_BACKEND_DSN__,
    FINANZE_ENVIRONMENT: environment,
  }
}

export function setTelemetryConsent(next: {
  errorReporting: boolean
  sessionReplay: boolean
  installId?: string
}): TelemetryConsent {
  consent = {
    errorReporting: next.errorReporting,
    sessionReplay: next.errorReporting && next.sessionReplay,
    installId: next.installId || consent.installId || randomUUID(),
  }

  writeConsent(consent)
  return { ...consent }
}

export function captureException(
  error: unknown,
  tags?: Record<string, string>,
): void {
  if (!isTelemetryEnabled()) return

  const parsed = parseDsn(dsn)
  if (!parsed) return

  const err = error instanceof Error ? error : new Error(String(error))
  const frames = parseStack(err.stack)

  const event = {
    event_id: randomUUID().replace(/-/g, ""),
    timestamp: Date.now() / 1000,
    platform: "node",
    level: "error",
    environment,
    release: __APP_VERSION__,
    user: consent.installId ? { id: consent.installId } : undefined,
    tags: { component: "electron-main", ...tags },
    exception: {
      values: [
        {
          type: err.name,
          value: scrub(err.message),
          stacktrace: frames.length ? { frames } : undefined,
        },
      ],
    },
  }

  const body =
    `${JSON.stringify({ event_id: event.event_id, sent_at: new Date().toISOString() })}\n` +
    `${JSON.stringify({ type: "event" })}\n` +
    `${JSON.stringify(event)}\n`

  fetch(parsed.endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-sentry-envelope" },
    body,
  }).catch(() => undefined)
}

export function initTelemetry(): void {
  dsn = __BS_ELECTRON_MAIN_DSN__
  environment = __BS_ENVIRONMENT__ || "production"

  consent = readConsent()
  if (!consent.installId) {
    consent.installId = randomUUID()
  }

  process.on("uncaughtException", error => {
    console.error("Uncaught exception in main process:", error)
    captureException(error, { phase: "uncaught_exception" })
  })

  process.on("unhandledRejection", reason => {
    console.error("Unhandled rejection in main process:", reason)
    captureException(reason, { phase: "unhandled_rejection" })
  })
}
