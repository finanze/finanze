export interface SentryStackFrame {
  filename?: string
  function?: string
  lineno?: number
  context_line?: string
}

export interface SentryExceptionPayload {
  type: string
  value: string
  level?: "error" | "warning" | "info"
  frames?: SentryStackFrame[]
  tags?: Record<string, string>
  extra?: Record<string, unknown>
}

export interface SentryEventOptions {
  platform: "python" | "javascript" | "node"
  environment?: string
  release?: string
  installId?: string
  serverName?: string
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
  return crypto.randomUUID().replace(/-/g, "")
}

export function buildEvent(
  payload: SentryExceptionPayload,
  options: SentryEventOptions,
): Record<string, unknown> {
  const event: Record<string, unknown> = {
    event_id: randomEventId(),
    timestamp: Date.now() / 1000,
    platform: options.platform,
    level: payload.level ?? "error",
    exception: {
      values: [
        {
          type: payload.type,
          value: payload.value,
          stacktrace: payload.frames?.length
            ? { frames: payload.frames }
            : undefined,
        },
      ],
    },
  }

  if (options.environment) event.environment = options.environment
  if (options.release) event.release = options.release
  if (options.installId) event.user = { id: options.installId }
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
    return response.ok
  } catch {
    return false
  }
}
