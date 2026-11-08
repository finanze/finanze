import { isNativeMobile, isWeb } from "@/lib/platform"
import { openInAppBrowser, closeInAppBrowser } from "@/lib/mobile"

export const INTEGRATION_OAUTH_PARAM = "integration_oauth"

const INTEGRATION_COMPLETE_DEEPLINK = "finanze://integration/complete"
const LOOPBACK_CALLBACK_PATH = "/auth/callback"

export interface IntegrationOAuthCallback {
  integrationId: string
  state: string | null
  code: string | null
  error: string | null
  clientId: string | null
}

export interface LoopbackAuthorization {
  callbackUrl: string
  wait(link: string): Promise<IntegrationOAuthCallback | null>
  cancel(): Promise<void>
}

export async function openExternalAuthLink(link: string) {
  if (isNativeMobile()) {
    try {
      await openInAppBrowser(link)
    } catch {
      // ignore in-app browser open errors
    }
    return
  }
  if (isWeb()) {
    // Web/Docker: navigate the same tab; the provider page redirects back
    // to this app with the code/state once the authorization completes.
    window.location.assign(link)
    return
  }
  try {
    window.open(link, "_blank")
  } catch {
    // ignore window open errors
  }
}

export async function closeExternalAuthBrowser() {
  try {
    await closeInAppBrowser()
  } catch {
    // ignore in-app browser close errors
  }
}

export async function openExternalAuthPage(link: string) {
  if (isNativeMobile()) {
    try {
      await openInAppBrowser(link)
    } catch {
      // ignore in-app browser open errors
    }
    return
  }
  try {
    window.open(link, "_blank", "noopener,noreferrer")
  } catch {
    // ignore window open errors
  }
}

export function buildIntegrationCompletionUrl(integrationId: string): string {
  const query = `${INTEGRATION_OAUTH_PARAM}=${encodeURIComponent(integrationId)}`
  if (isWeb()) {
    const route = `#/entities?tab=providers&focus=${encodeURIComponent(integrationId)}`
    return `${window.location.origin}${window.location.pathname}?${query}${route}`
  }
  return `${INTEGRATION_COMPLETE_DEEPLINK}?${query}`
}

export function parseIntegrationOAuthCallback(
  search: string,
): IntegrationOAuthCallback | null {
  const params = new URLSearchParams(search)
  const integrationId = params.get(INTEGRATION_OAUTH_PARAM)
  if (!integrationId) return null
  return {
    integrationId,
    state: params.get("state"),
    code: params.get("code"),
    error: params.get("error"),
    clientId: params.get("client_id"),
  }
}

export function parseOAuthCallbackAddress(
  integrationId: string,
  address: string,
): IntegrationOAuthCallback | null {
  let url: URL
  try {
    url = new URL(address.trim())
  } catch {
    return null
  }
  const state = url.searchParams.get("state")
  if (!state) return null
  return {
    integrationId,
    state,
    code: url.searchParams.get("code"),
    error: url.searchParams.get("error"),
    clientId: url.searchParams.get("client_id"),
  }
}

function authorizationState(link: string): string | null {
  try {
    return new URL(link).searchParams.get("state")
  } catch {
    return null
  }
}

export async function startLoopbackAuthorization(
  integrationId: string,
): Promise<LoopbackAuthorization> {
  const { LoopbackCallback } = await import("@/lib/capacitor/loopbackCallback")
  const { Browser } = await import("@capacitor/browser")

  let settle: (callback: IntegrationOAuthCallback | null) => void = () => {}
  const outcome = new Promise<IntegrationOAuthCallback | null>(resolve => {
    settle = resolve
  })
  let expectedState: string | null = null
  let released = false

  const handles = await Promise.all([
    LoopbackCallback.addListener("callback", ({ url }) => {
      const callback = parseOAuthCallbackAddress(integrationId, url)
      if (callback && expectedState && callback.state === expectedState) {
        settle(callback)
      }
    }),
    LoopbackCallback.addListener("timeout", () => settle(null)),
    Browser.addListener("browserFinished", () => settle(null)),
  ])

  const release = async () => {
    if (released) return
    released = true
    await Promise.all(handles.map(handle => handle.remove()))
    try {
      await LoopbackCallback.stop()
    } catch {
      // listener already stopped
    }
  }

  let callbackUrl: string
  try {
    callbackUrl = (
      await LoopbackCallback.start({ path: LOOPBACK_CALLBACK_PATH })
    ).url
  } catch (error) {
    await release()
    throw error
  }

  return {
    callbackUrl,
    async wait(link: string) {
      expectedState = authorizationState(link)
      await openExternalAuthLink(link)
      const callback = await outcome
      await release()
      if (callback) {
        await closeExternalAuthBrowser()
      }
      return callback
    },
    async cancel() {
      settle(null)
      await release()
    },
  }
}
