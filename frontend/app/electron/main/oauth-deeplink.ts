import type { App, BrowserWindow } from "electron"

export const OAUTH_PROTOCOL_NAME = "finanze"

type OAuthTokens = {
  access_token: string
  refresh_token: string
  type?: string
}

type OAuthError = {
  error: string
  error_description: string | null
  error_code: string | null
}

type OAuthCode = {
  code: string
}

function registerProtocolClient(app: App) {
  console.debug("[OAuth] Registering protocol client:", OAUTH_PROTOCOL_NAME)
  if (process.defaultApp) {
    if (process.argv.length >= 2) {
      app.setAsDefaultProtocolClient(OAUTH_PROTOCOL_NAME, process.execPath, [
        process.argv[1],
      ])
      console.debug("[OAuth] Registered as default protocol client (dev mode)")
    }
  } else {
    app.setAsDefaultProtocolClient(OAUTH_PROTOCOL_NAME)
    console.debug("[OAuth] Registered as default protocol client (production)")
  }
}

function parseOAuthTokens(url: string): OAuthTokens | null {
  console.debug(
    "[OAuth] Parsing tokens from URL:",
    url.substring(0, 50) + "...",
  )
  try {
    const urlObj = new URL(url)
    const hash = urlObj.hash.startsWith("#")
      ? urlObj.hash.substring(1)
      : urlObj.hash
    const hashParams = new URLSearchParams(hash)
    console.debug(
      "[OAuth] Extracted hash parameters from URL:",
      hashParams.values(),
    )
    const accessToken = hashParams.get("access_token")
    const refreshToken = hashParams.get("refresh_token")
    const type = hashParams.get("type") ?? undefined

    if (!accessToken || !refreshToken) {
      console.warn(
        "[OAuth] Missing tokens in URL - accessToken:",
        !!accessToken,
        "refreshToken:",
        !!refreshToken,
      )
      return null
    }

    console.debug("[OAuth] Successfully parsed OAuth tokens")
    return { access_token: accessToken, refresh_token: refreshToken, type }
  } catch (error) {
    console.error("[OAuth] Failed to parse OAuth URL:", error)
    return null
  }
}

function parseOAuthError(url: string): OAuthError | null {
  try {
    const urlObj = new URL(url)
    const error = urlObj.searchParams.get("error")

    if (!error) {
      return null
    }

    return {
      error,
      error_description: urlObj.searchParams.get("error_description"),
      error_code: urlObj.searchParams.get("error_code"),
    }
  } catch (err) {
    console.error("[OAuth] Failed to parse OAuth error URL:", err)
    return {
      error: "invalid_callback_url",
      error_description: null,
      error_code: null,
    }
  }
}

function parseOAuthCode(url: string): OAuthCode | null {
  try {
    const urlObj = new URL(url)
    const code = urlObj.searchParams.get("code")
    if (!code) {
      return null
    }
    return { code }
  } catch (err) {
    console.error("[OAuth] Failed to parse OAuth code URL:", err)
    return null
  }
}

function focusWindow(window: BrowserWindow | null) {
  if (!window) {
    return
  }

  if (window.isMinimized()) {
    window.restore()
  }

  window.focus()
}

export function setupOAuthDeepLinking(options: {
  app: App
  getMainWindow: () => BrowserWindow | null
  sendToAllWindows: (channel: string, ...args: any[]) => void
}) {
  const { app, getMainWindow, sendToAllWindows } = options

  registerProtocolClient(app)

  const handleUrl = (url: string) => {
    console.debug("[OAuth] Handling OAuth URL callback")

    // Always forward the full URL to the renderer so Supabase can parse it.
    // This avoids mixing flows (oauth, recovery, signup confirmation) and keeps
    // parsing logic in one place.
    console.debug("[OAuth] Sending oauth-callback-url IPC message to renderer")
    sendToAllWindows("oauth-callback-url", { url })

    const oauthError = parseOAuthError(url)
    if (oauthError) {
      console.warn(
        "[OAuth] OAuth callback returned error:",
        oauthError.error,
        oauthError.error_code,
        oauthError.error_description,
      )
      console.debug(
        "[OAuth] Sending oauth-callback-error IPC message to renderer",
      )
      sendToAllWindows("oauth-callback-error", oauthError)
      console.debug("[OAuth] Focusing main window")
      focusWindow(getMainWindow())
      return
    }

    const oauthCode = parseOAuthCode(url)
    if (oauthCode) {
      console.debug("[OAuth] OAuth callback returned code")
      console.debug(
        "[OAuth] Sending oauth-callback-code IPC message to renderer",
      )
      sendToAllWindows("oauth-callback-code", oauthCode)
      console.debug("[OAuth] Focusing main window")
      focusWindow(getMainWindow())
      return
    }

    const tokens = parseOAuthTokens(url)
    if (!tokens) {
      console.warn("[OAuth] No valid tokens extracted from URL")
      console.debug(
        "[OAuth] Sending oauth-callback-error IPC message to renderer",
      )
      sendToAllWindows("oauth-callback-error", {
        error: "missing_tokens",
        error_description: null,
        error_code: null,
      } satisfies OAuthError)
      console.debug("[OAuth] Focusing main window")
      focusWindow(getMainWindow())
      return
    }

    console.debug("[OAuth] Sending oauth-callback IPC message to renderer")
    sendToAllWindows("oauth-callback", tokens)
    console.debug("[OAuth] Focusing main window")
    focusWindow(getMainWindow())
  }

  app.on("open-url", (event, url) => {
    console.debug(
      "[OAuth] open-url event received:",
      url.substring(0, 50) + "...",
    )
    event.preventDefault()
    handleUrl(url)
  })

  app.on("second-instance", (_, commandLine) => {
    console.debug("[OAuth] second-instance event received")
    focusWindow(getMainWindow())

    const url = commandLine.find(arg =>
      arg.startsWith(`${OAUTH_PROTOCOL_NAME}://`),
    )
    if (url) {
      console.debug(
        "[OAuth] Found OAuth URL in command line:",
        url.substring(0, 50) + "...",
      )
      handleUrl(url)
    } else {
      console.debug("[OAuth] No OAuth URL found in command line")
    }
  })

  const initialUrl = process.argv.find(arg =>
    arg.startsWith(`${OAUTH_PROTOCOL_NAME}://`),
  )
  if (initialUrl) {
    console.debug(
      "[OAuth] Found initial OAuth URL in process.argv:",
      initialUrl.substring(0, 50) + "...",
    )
    handleUrl(initialUrl)
  }
}
