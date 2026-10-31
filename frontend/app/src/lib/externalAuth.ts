import { isNativeMobile, isWeb } from "@/lib/platform"
import { openInAppBrowser, closeInAppBrowser } from "@/lib/mobile"

export const INTEGRATION_OAUTH_PARAM = "integration_oauth"

const INTEGRATION_COMPLETE_DEEPLINK = "finanze://integration/complete"

export interface IntegrationOAuthCallback {
  integrationId: string
  state: string | null
  code: string | null
  error: string | null
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
  }
}
