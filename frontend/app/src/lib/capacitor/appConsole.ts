import { Capacitor } from "@capacitor/core"

const MAX_JSON_CHARS = 4000
const MAX_STRING_CHARS = 2000

function isNativeMobile(): boolean {
  const platform = Capacitor.getPlatform()
  return platform === "android" || platform === "ios"
}

function truncateString(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value
  return value.slice(0, maxChars) + "…(truncated)"
}

function safeJsonStringify(value: unknown): string {
  const seen = new WeakSet<object>()

  const json = JSON.stringify(
    value,
    (_key, val) => {
      if (typeof val === "string") {
        return truncateString(val, 500)
      }

      if (val instanceof Date) {
        return val.toISOString()
      }

      if (val instanceof Error) {
        return {
          name: val.name,
          message: val.message,
          stack: val.stack,
        }
      }

      if (val instanceof Uint8Array) {
        return `Uint8Array(${val.byteLength})`
      }

      if (val instanceof ArrayBuffer) {
        return `ArrayBuffer(${val.byteLength})`
      }

      if (ArrayBuffer.isView(val)) {
        return `${(val as any)?.constructor?.name ?? "TypedArray"}(${(val as any)?.byteLength ?? 0})`
      }

      if (typeof Blob !== "undefined" && val instanceof Blob) {
        return `Blob(${val.type || "application/octet-stream"}, ${val.size})`
      }

      if (val && typeof val === "object") {
        if (seen.has(val as object)) {
          return "[Circular]"
        }
        seen.add(val as object)
      }

      return val
    },
    2,
  )

  return truncateString(json, MAX_JSON_CHARS)
}

export function formatConsoleArg(value: unknown): unknown {
  if (!isNativeMobile()) return value

  if (value === null) return "null"
  if (value === undefined) return "undefined"

  if (typeof value === "string") return truncateString(value, MAX_STRING_CHARS)
  if (typeof value === "number")
    return Number.isFinite(value) ? String(value) : String(value)
  if (typeof value === "boolean" || typeof value === "bigint")
    return String(value)

  if (value instanceof Error) {
    const stack = value.stack ? `\n${value.stack}` : ""
    return `${value.name}: ${value.message}${stack}`
  }

  if (value instanceof Uint8Array) return `Uint8Array(${value.byteLength})`
  if (value instanceof ArrayBuffer) return `ArrayBuffer(${value.byteLength})`
  if (ArrayBuffer.isView(value)) {
    const ctor = (value as any)?.constructor?.name ?? "TypedArray"
    const len = (value as any)?.byteLength ?? 0
    return `${ctor}(${len})`
  }

  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return `Blob(${value.type || "application/octet-stream"}, ${value.size})`
  }

  if (typeof value === "object") {
    try {
      return safeJsonStringify(value)
    } catch {
      try {
        return String(value)
      } catch {
        return "[Unserializable]"
      }
    }
  }

  return String(value)
}

function formatArgsForConsole(args: unknown[]): unknown[] {
  if (!isNativeMobile()) return args
  return args.map(formatConsoleArg)
}

export const appConsole = {
  debug: (message: string, ...args: unknown[]) => {
    if (!isNativeMobile()) {
      console.debug(message, ...args)
      return
    }

    console.debug(message, ...formatArgsForConsole(args))
  },

  info: (message: string, ...args: unknown[]) => {
    console.info(message, ...formatArgsForConsole(args))
  },

  warn: (message: string, ...args: unknown[]) => {
    console.warn(message, ...formatArgsForConsole(args))
  },

  error: (message: string, ...args: unknown[]) => {
    console.error(message, ...formatArgsForConsole(args))
  },
}
