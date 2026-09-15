import { app } from "electron"
import { homedir } from "node:os"
import { join } from "node:path"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { randomUUID } from "node:crypto"

import { getElectronPlatformInfo } from "../shared/platform"
import { OS } from "../types"

const CONSENT_FILE = "telemetry.json"
const REDACTED = "[redacted]"
const MAX_FRAMES = 30
const MAX_CAUSES = 3

// Kept aligned with the backend OS enum so events can be filtered across components.
const OS_TAGS: Record<OS, string> = {
  [OS.MAC]: "MACOS",
  [OS.WINDOWS]: "WINDOWS",
  [OS.LINUX]: "LINUX",
}

const OS_NAMES: Record<OS, string> = {
  [OS.MAC]: "macOS",
  [OS.WINDOWS]: "Windows",
  [OS.LINUX]: "Linux",
}

const EMAIL_RE = /[\w.+-]+@[\w-]+\.[\w.]+/g
const LONG_HEX_RE = /\b[0-9a-fA-F]{26,}\b/g
const IBAN_RE = /\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b/g

export interface TelemetryConsent {
  errorReporting: boolean
  installId: string
}

let consent: TelemetryConsent = {
  errorReporting: false,
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
      installId: typeof raw.install_id === "string" ? raw.install_id : "",
    }
  } catch {
    return { errorReporting: false, installId: "" }
  }
}

function writeConsent(value: TelemetryConsent): void {
  const payload = {
    error_reporting: value.errorReporting,
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
  abs_path?: string
  function?: string
  lineno?: number
  colno?: number
  in_app?: boolean
}

interface DebugImage {
  type: "sourcemap"
  code_file: string
  debug_id: string
}

function parseStack(stack: string | undefined): Frame[] {
  if (!stack) return []

  const frames: Frame[] = []
  for (const line of stack.split("\n").slice(1)) {
    const match = line
      .trim()
      .match(/^at\s+(?:(.+?)\s+\()?(.+?):(\d+):(\d+)\)?$/)
    if (!match) continue

    const filename = scrub(match[2])
    frames.push({
      function: match[1],
      filename,
      abs_path: filename,
      lineno: Number(match[3]),
      colno: Number(match[4]),
      in_app: !filename.includes("node_modules"),
    })
  }

  return frames.slice(0, MAX_FRAMES).reverse()
}

interface ExceptionValue {
  type: string
  value: string
  frames: Frame[]
}

function causeChain(error: Error): ExceptionValue[] {
  const chain: ExceptionValue[] = []
  let current: unknown = error

  while (current instanceof Error && chain.length <= MAX_CAUSES) {
    chain.push({
      type: current.name,
      value: scrub(current.message),
      frames: parseStack(current.stack),
    })
    current = current.cause
  }

  return chain
}

// The bundler injects a stack-keyed debug id per chunk; without these images the
// uploaded source maps cannot be matched back to the minified files.
function debugImagesFor(frames: Frame[]): DebugImage[] {
  const debugIds = (globalThis as { _sentryDebugIds?: Record<string, string> })
    ._sentryDebugIds
  if (!debugIds) return []

  const idByFile = new Map<string, string>()
  for (const [stack, debugId] of Object.entries(debugIds)) {
    const file = parseStack(stack).pop()?.abs_path
    if (file) idByFile.set(file, debugId)
  }

  const images: DebugImage[] = []
  const seen = new Set<string>()
  for (const frame of frames) {
    const file = frame.abs_path
    if (!file || seen.has(file)) continue
    const debugId = idByFile.get(file)
    if (!debugId) continue

    seen.add(file)
    images.push({ type: "sourcemap", code_file: file, debug_id: debugId })
  }

  return images
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
  installId?: string
}): TelemetryConsent {
  consent = {
    errorReporting: next.errorReporting,
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
  const chain = causeChain(err)
  // Wrapped errors bury the real one in `cause`, so lead with the first that
  // has app frames instead of the outermost.
  const primaryIndex = chain.findIndex(entry =>
    entry.frames.some(frame => frame.in_app),
  )
  const primary = chain[primaryIndex === -1 ? 0 : primaryIndex]
  const values = [...chain.filter(entry => entry !== primary), primary].map(
    entry => ({
      type: entry.type,
      value: entry.value,
      stacktrace: entry.frames.length ? { frames: entry.frames } : undefined,
    }),
  )
  const debugImages = debugImagesFor(chain.flatMap(entry => entry.frames))
  const platformInfo = getElectronPlatformInfo()

  const event = {
    event_id: randomUUID().replace(/-/g, ""),
    timestamp: Date.now() / 1000,
    platform: "node",
    level: "error",
    environment,
    release: __APP_VERSION__,
    user: consent.installId ? { id: consent.installId } : undefined,
    tags: {
      component: "electron-main",
      distribution: "desktop",
      platform_os: OS_TAGS[platformInfo.type],
      ...(platformInfo.osVersion ? { os_version: platformInfo.osVersion } : {}),
      ...tags,
    },
    contexts: {
      os: {
        name: OS_NAMES[platformInfo.type],
        version: platformInfo.osVersion,
      },
    },
    debug_meta: debugImages.length ? { images: debugImages } : undefined,
    exception: { values },
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
