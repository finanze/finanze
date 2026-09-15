import { randomUuid } from "@/lib/telemetry/uuid"

export interface SentryStackFrame {
  filename?: string
  abs_path?: string
  function?: string
  lineno?: number
  colno?: number
  in_app?: boolean
  context_line?: string
  vars?: Record<string, string>
}

export interface SentryExceptionValue {
  type: string
  value: string
  frames?: SentryStackFrame[]
}

export interface SentryExceptionPayload extends SentryExceptionValue {
  level?: "error" | "warning" | "info"
  tags?: Record<string, string>
  extra?: Record<string, unknown>
  causes?: SentryExceptionValue[]
}

export interface SentryDebugImage {
  type: "sourcemap"
  code_file: string
  debug_id: string
}

export interface SentryOsContext {
  name: string
  version?: string
}

export interface SentryEventOptions {
  platform: "python" | "javascript" | "node"
  environment?: string
  release?: string
  installId?: string
  userId?: string
  osContext?: SentryOsContext
  debugImages?: SentryDebugImage[]
}

interface ParsedDsn {
  host: string
  projectId: string
  publicKey: string
  protocol: string
}

export function parseDsn(dsn: string): ParsedDsn | null {
  try {
    const url = new URL(dsn)
    const projectId = url.pathname.replace(/^\//, "")
    if (!url.username || !projectId) return null

    return {
      host: url.host,
      projectId,
      publicKey: url.username,
      protocol: url.protocol.replace(":", ""),
    }
  } catch {
    return null
  }
}

function randomEventId(): string {
  return randomUuid().replace(/-/g, "")
}

export function buildEvent(
  payload: SentryExceptionPayload,
  options: SentryEventOptions,
): Record<string, unknown> {
  const values = [...(payload.causes ?? []), payload].map(value => ({
    type: value.type,
    value: value.value,
    stacktrace: value.frames?.length ? { frames: value.frames } : undefined,
  }))

  const event: Record<string, unknown> = {
    event_id: randomEventId(),
    timestamp: Date.now() / 1000,
    platform: options.platform,
    level: payload.level ?? "error",
    exception: { values },
  }

  if (options.environment) event.environment = options.environment
  if (options.release) event.release = options.release
  // The install id is the only identifier always available, so it stays the
  // primary one; the hashed user id is only known once logged in.
  const identity = options.installId ?? options.userId
  if (identity) {
    event.user = {
      id: identity,
      ...(options.userId ? { user_id: options.userId } : {}),
    }
  }
  if (options.debugImages?.length) {
    event.debug_meta = { images: options.debugImages }
  }
  if (options.osContext) {
    event.contexts = { os: options.osContext }
  }
  if (payload.tags) event.tags = payload.tags
  if (payload.extra) event.extra = payload.extra

  return event
}

export async function sendEvent(
  dsn: string,
  event: Record<string, unknown>,
): Promise<boolean> {
  const parsed = parseDsn(dsn)
  if (!parsed) return false

  const endpoint =
    `${parsed.protocol}://${parsed.host}/api/${parsed.projectId}/envelope/` +
    `?sentry_key=${parsed.publicKey}&sentry_version=7&sentry_client=finanze`

  const header = {
    event_id: event.event_id,
    sent_at: new Date().toISOString(),
  }

  const body =
    `${JSON.stringify(header)}\n` +
    `${JSON.stringify({ type: "event" })}\n` +
    `${JSON.stringify(event)}\n`

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/x-sentry-envelope" },
      body,
    })
    if (!response.ok) {
      console.warn("[Telemetry] Report rejected by ingest", response.status)
    }
    return response.ok
  } catch (error) {
    console.warn("[Telemetry] Report could not be delivered", error)
    return false
  }
}
