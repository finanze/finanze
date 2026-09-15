import { BS_ENVIRONMENT, BS_FRONTEND_DSN } from "@/env"
import { getPlatformInfo, isNativeMobile } from "@/lib/platform"
import { PlatformType } from "@/types"

import { getCachedConsent, loadConsent } from "./consent"
import {
  buildEvent,
  sendEvent,
  type SentryDebugImage,
  type SentryExceptionValue,
  type SentryOsContext,
  type SentryStackFrame,
} from "./sentryEnvelope"

const REDACTED = "[redacted]"
const MAX_FRAMES = 30
const MAX_CAUSES = 3
const DEDUPE_WINDOW_MS = 10_000

const EMAIL_RE = /[\w.+-]+@[\w-]+\.[\w.]+/g
const LONG_HEX_RE = /\b[0-9a-fA-F]{26,}\b/g
const IBAN_RE = /\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b/g

// V8/Chromium: "at fn (url:line:col)" - WebKit/Gecko: "fn@url:line:col"
const V8_FRAME_RE = /^at\s+(?:(.+?)\s+\()?(.+?):(\d+):(\d+)\)?$/
const WEBKIT_FRAME_RE = /^(?:(.*?)@)?(\S+?):(\d+):(\d+)$/

// Kept aligned with the backend OS enum so events can be filtered across components.
const PLATFORM_OS: Partial<Record<PlatformType, string>> = {
  [PlatformType.WINDOWS]: "WINDOWS",
  [PlatformType.MAC]: "MACOS",
  [PlatformType.LINUX]: "LINUX",
  [PlatformType.IOS]: "IOS",
  [PlatformType.ANDROID]: "ANDROID",
}

const OS_NAMES: Record<string, string> = {
  WINDOWS: "Windows",
  MACOS: "macOS",
  LINUX: "Linux",
  IOS: "iOS",
  ANDROID: "Android",
}

let listenersAttached = false
let userId: string | undefined
let backendVersion: string | undefined
let backendOs: string | undefined
let backendOsVersion: string | undefined

const recentEvents = new Map<string, number>()

export function setTelemetryContext(context: {
  userId?: string | null
  backendVersion?: string | null
  backendOs?: string | null
  backendOsVersion?: string | null
}): void {
  userId = context.userId ?? undefined
  backendVersion = context.backendVersion ?? undefined
  backendOs = context.backendOs ?? undefined
  backendOsVersion = context.backendOsVersion ?? undefined
}

function distribution(): string {
  if (window.ipcAPI) return "desktop"
  if (isNativeMobile()) return "mobile"
  return "web"
}

// On web the browser exposes no OS, so the backend one is reported instead.
function operatingSystem(): { os?: string; version?: string } {
  const info = getPlatformInfo()
  const os = PLATFORM_OS[info.type]
  if (os) return { os, version: info.osVersion }

  return { os: backendOs, version: backendOsVersion }
}

function osContext(os?: string, version?: string): SentryOsContext | undefined {
  if (!os) return undefined
  return { name: OS_NAMES[os] ?? os, version }
}

function toError(value: unknown): Error {
  if (value instanceof Error) return value
  if (typeof value === "string") return new Error(value)

  try {
    return new Error(JSON.stringify(value))
  } catch {
    return new Error(Object.prototype.toString.call(value))
  }
}

function causeChain(error: Error): SentryExceptionValue[] {
  const chain: SentryExceptionValue[] = []
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

function isDuplicate(key: string): boolean {
  const now = Date.now()
  for (const [seenKey, seenAt] of recentEvents) {
    if (now - seenAt > DEDUPE_WINDOW_MS) recentEvents.delete(seenKey)
  }

  if (recentEvents.has(key)) return true

  recentEvents.set(key, now)
  return false
}

function scrub(text: string): string {
  return text
    .replace(EMAIL_RE, REDACTED)
    .replace(IBAN_RE, REDACTED)
    .replace(LONG_HEX_RE, REDACTED)
    .slice(0, 2000)
}

function parseStack(stack: string | undefined): SentryStackFrame[] {
  if (!stack) return []

  const frames: SentryStackFrame[] = []
  for (const rawLine of stack.split("\n")) {
    const line = rawLine.trim()
    const match = line.match(V8_FRAME_RE) ?? line.match(WEBKIT_FRAME_RE)
    if (!match) continue

    const filename = scrub(match[2])
    frames.push({
      function: match[1] || undefined,
      filename,
      abs_path: filename,
      lineno: Number(match[3]),
      colno: Number(match[4]),
      in_app: !filename.includes("node_modules"),
    })
  }

  return frames.slice(0, MAX_FRAMES).reverse()
}

// The bundler injects a stack-keyed debug id per chunk; without these images the
// uploaded source maps cannot be matched back to the minified files.
function debugImagesFor(frames: SentryStackFrame[]): SentryDebugImage[] {
  const debugIds = (
    window as Window & { _sentryDebugIds?: Record<string, string> }
  )._sentryDebugIds
  if (!debugIds) return []

  const idByFile = new Map<string, string>()
  for (const [stack, debugId] of Object.entries(debugIds)) {
    const file = parseStack(stack).pop()?.abs_path
    if (file) idByFile.set(file, debugId)
  }

  const images: SentryDebugImage[] = []
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

function isEnabled(): boolean {
  return !!BS_FRONTEND_DSN && getCachedConsent()?.errorReporting === true
}

export function reportError(
  error: unknown,
  tags?: Record<string, string>,
  extra?: Record<string, unknown>,
): void {
  if (!BS_FRONTEND_DSN) return

  if (!getCachedConsent()) {
    // Crashes during startup happen before the stored consent has been read.
    void loadConsent().then(consent => {
      if (consent.errorReporting) emit(error, tags, extra)
    })
    return
  }

  if (!isEnabled()) return
  emit(error, tags, extra)
}

function emit(
  error: unknown,
  tags?: Record<string, string>,
  extra?: Record<string, unknown>,
): void {
  const chain = causeChain(toError(error))
  // React rethrows render failures wrapped in an error of its own, so the
  // reported one is the first with app frames instead of the outermost.
  const primaryIndex = chain.findIndex(entry =>
    entry.frames?.some(frame => frame.in_app),
  )
  const primary = chain[primaryIndex === -1 ? 0 : primaryIndex]
  const causes = chain.filter(entry => entry !== primary)
  const frames = primary.frames ?? []
  const topFrame = frames[frames.length - 1]

  if (
    isDuplicate(
      `${primary.type}|${primary.value}|${topFrame?.filename}:${topFrame?.lineno}:${topFrame?.colno}`,
    )
  ) {
    return
  }

  const { os, version: osVersion } = operatingSystem()
  const allFrames = chain.flatMap(entry => entry.frames ?? [])

  const event = buildEvent(
    {
      type: primary.type,
      value: primary.value,
      frames,
      causes,
      extra,
      tags: {
        component: "renderer",
        distribution: distribution(),
        ...(os ? { platform_os: os } : {}),
        ...(osVersion ? { os_version: osVersion } : {}),
        ...(userId ? { user_id: userId } : {}),
        ...(backendVersion ? { backend_version: backendVersion } : {}),
        ...tags,
      },
    },
    {
      platform: "javascript",
      environment: BS_ENVIRONMENT,
      release: __APP_VERSION__,
      installId: getCachedConsent()?.installId,
      userId,
      osContext: osContext(os, osVersion),
      debugImages: debugImagesFor(allFrames),
    },
  )

  void sendEvent(BS_FRONTEND_DSN, event)
}

export async function initRendererTelemetry(): Promise<void> {
  await loadConsent()
  if (!BS_FRONTEND_DSN || listenersAttached) return

  listenersAttached = true

  window.addEventListener("error", event => {
    reportError(event.error ?? event.message, { phase: "window_error" })
  })
  window.addEventListener("unhandledrejection", event => {
    reportError(event.reason, { phase: "unhandled_rejection" })
  })
}
