type BetterstackFn = ((...args: unknown[]) => void) & {
  q?: unknown[][]
  l?: number
}

declare global {
  interface Window {
    betterstack?: BetterstackFn
  }
}

export interface TagOptions {
  token: string
  environment: string
  release?: string
  sessionReplay: boolean
  installId?: string
}

let loaded = false

export function isTagLoaded(): boolean {
  return loaded
}

export function loadTag(options: TagOptions): void {
  if (loaded || !options.token) return

  const queue: BetterstackFn = function (...args: unknown[]) {
    ;(queue.q = queue.q || []).push(args)
  }
  queue.l = Date.now()
  window.betterstack = window.betterstack ?? queue

  const script = document.createElement("script")
  script.async = true
  script.crossOrigin = "anonymous"
  script.src = `https://betterstack.net/b.js?t=${encodeURIComponent(options.token)}`
  document.head.appendChild(script)

  // Session replay has no snippet-level switch, so it is turned off through the
  // underlying Sentry replay sample rates when the user did not consent to it.
  window.betterstack("config", {
    environment: options.environment,
    release: options.release,
    sentry: options.sessionReplay
      ? {
          replaysSessionSampleRate: 0,
          replaysOnErrorSampleRate: 1,
          replayIntegrationOptions: {
            maskAllText: true,
            maskAllInputs: true,
            blockAllMedia: true,
            mask: ["[data-pii]"],
            block: ["[data-pii-block]"],
          },
        }
      : { replaysSessionSampleRate: 0, replaysOnErrorSampleRate: 0 },
  })

  window.betterstack("init", {
    environment: options.environment,
    release: options.release,
  })

  loaded = true

  if (options.installId) identifyUser(options.installId)
}

export function identifyUser(installId: string): void {
  window.betterstack?.("user", { id: installId })
}

export function clearUser(): void {
  window.betterstack?.("user", null)
}

export function reportError(error: unknown): void {
  if (!loaded) return

  setTimeout(() => {
    throw error
  })
}
