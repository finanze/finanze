import { randomUUID } from "node:crypto"
import { BrowserView, BrowserWindow, ipcMain, session } from "electron"
import {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "."

export const UNICAJA_ID = "e0000000-0000-0000-0000-000000000002"

const UNICAJA_BASE_URL = "https://univia.unicajabanco.es"
const OAUTH_TOKEN_URL = `${UNICAJA_BASE_URL}/apis/externo/unicaja/univia/oauth2/token`
const UNICAJA_USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const unicajaPartition = `unicaja-${randomUUID()}`
  const unicajaSession = session.fromPartition(unicajaPartition)

  unicajaSession.setUserAgent(UNICAJA_USER_AGENT, "es-ES,es;q=0.9,en;q=0.8")

  let unicajaWindow: BrowserWindow | null = new BrowserWindow({
    width: 1100,
    height: 700,
    show: true,
    webPreferences: {
      partition: unicajaPartition,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  })
  const unicajaView = new BrowserView({
    webPreferences: {
      partition: unicajaPartition,
      defaultEncoding: "utf-8",
      nodeIntegration: false,
      nodeIntegrationInSubFrames: true,
      sandbox: true,
      webviewTag: false,
      contextIsolation: true,
      enableBlinkFeatures: [
        "WebBluetooth",
        "WebBluetoothGetDevices",
        "WebBluetoothRemoteCharacteristicNewWriteValue",
        "WebBluetoothWatchAdvertisements",
        "CSSModules",
      ].join(","),
    },
  })
  unicajaWindow.setBrowserView(unicajaView)
  unicajaView.setBounds({ x: 0, y: 0, width: 1100, height: 700 })
  const unicajaWebContents = unicajaView.webContents

  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
    flow: request.flow,
  }
  let completed = false
  function sendCompletion(r: LoginHandlerResult) {
    if (completed) return
    completed = true
    console.debug("Sending completion for Unicaja:", UNICAJA_ID)
    ipcMain.emit("completed-external-login", null, UNICAJA_ID, r)
  }

  async function readCapturedCredentials() {
    try {
      const captured = await unicajaWebContents.executeJavaScript(
        "window.__finanzeUnicajaCredentials || null",
      )
      if (captured?.user) result.credentials.user = captured.user
      if (captured?.password) result.credentials.password = captured.password
    } catch (error) {
      console.warn("Could not read Unicaja form credentials:", error)
    }
  }

  unicajaWindow.on("closed", () => {
    unicajaSession.webRequest.onBeforeRequest(null)
    unicajaWindow = null
    sendCompletion(result)
  })
  await unicajaSession.clearStorageData()

  function completeFromBrowserSession() {
    unicajaSession.cookies
      .get({ url: UNICAJA_BASE_URL })
      .then(async currentCookies => {
        await readCapturedCredentials()
        const abck = currentCookies.find(
          cookie => cookie.name === "_abck",
        )?.value
        if (abck) {
          result.credentials.abck = abck
        }
        result.success = Boolean(
          result.credentials.user &&
          result.credentials.password &&
          result.credentials.abck,
        )
        sendCompletion(result)
        unicajaWindow?.close()
      })
      .catch(error => {
        console.warn("Could not read Unicaja session cookie:", error)
      })
  }

  unicajaSession.webRequest.onCompleted(
    { urls: [OAUTH_TOKEN_URL] },
    details => {
      if (details.statusCode === 200) {
        completeFromBrowserSession()
      }
    },
  )

  unicajaSession.webRequest.onSendHeaders(
    { types: ["xhr"], urls: ["<all_urls>"] },
    details => {
      if (details.url.includes("/rest/autenticacion")) {
        void readCapturedCredentials()
      }
    },
  )

  const installCredentialCapture = () =>
    unicajaWebContents
      .executeJavaScript(
        `(() => {
        const install = () => {
          const username = document.querySelector('#username');
          const password = document.querySelector('#pwd');
          if (!(username instanceof HTMLInputElement) || !(password instanceof HTMLInputElement)) {
            return false;
          }
          if (password.dataset.finanzeCaptureInstalled === 'true') {
            return true;
          }
          const capture = () => {
            window.__finanzeUnicajaCredentials = {
              user: username.value,
              password: password.value,
            };
          };
          password.dataset.finanzeCaptureInstalled = 'true';
          username.addEventListener('input', capture, true);
          password.addEventListener('input', capture, true);
          password.addEventListener('change', capture, true);
          capture();
          return true;
        };

        if (install()) {
          return;
        }
        const observer = new MutationObserver(() => {
          if (install()) {
            observer.disconnect();
          }
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
      })()`,
      )
      .catch(error => {
        console.warn("Could not install Unicaja form capture:", error)
      })

  unicajaWebContents.on("dom-ready", () => {
    void installCredentialCapture()
    unicajaWindow?.show()
  })

  try {
    await unicajaWebContents.loadURL(`${UNICAJA_BASE_URL}/login`)
  } catch (error: any) {
    const isAborted =
      error?.message?.includes("ERR_ABORTED") ||
      error?.toString?.()?.includes("ERR_ABORTED")
    if (!isAborted) {
      console.error("Failed to load Unicaja login page:", error)
      unicajaWindow?.close()
      return { success: false }
    }
  }

  return { success: true }
}
