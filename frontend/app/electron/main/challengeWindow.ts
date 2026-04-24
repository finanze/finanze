import { BrowserWindow, ipcMain, session } from "electron"

export async function promptChallenge(
  siteKey: string,
  domain: string,
): Promise<{ success: boolean }> {
  const partition = "persist:challenge"
  const challengeSession = session.fromPartition(partition)
  await challengeSession.clearStorageData()

  let challengeWindow: BrowserWindow | null = new BrowserWindow({
    width: 450,
    height: 650,
    show: false,
    webPreferences: {
      partition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  let completed = false

  function sendCompletion(token: string | null) {
    if (completed) return
    completed = true
    ipcMain.emit("completed-challenge-window", null, token)
  }

  challengeWindow.once("ready-to-show", () => {
    challengeWindow?.show()
  })

  challengeWindow.on("closed", () => {
    if (!completed) {
      sendCompletion(null)
    }
    challengeWindow = null
  })

  const url = `https://${domain}`

  try {
    await challengeWindow.loadURL(url)
  } catch (error: any) {
    const isAborted =
      error?.message?.includes("ERR_ABORTED") ||
      error?.toString?.()?.includes("ERR_ABORTED")
    if (!isAborted) {
      console.error("Failed to load challenge page:", error)
      challengeWindow?.close()
      return { success: false }
    }
  }

  try {
    const token = await challengeWindow.webContents.executeJavaScript(`
      new Promise((resolve) => {
        document.body.innerHTML = '';
        document.body.style.cssText = 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f5f5f5;font-family:system-ui,sans-serif;';

        const container = document.createElement('div');
        container.style.cssText = 'text-align:center;';

        const title = document.createElement('p');
        title.textContent = 'Complete the security challenge';
        title.style.cssText = 'margin-bottom:20px;font-size:16px;color:#333;';
        container.appendChild(title);

        const recaptchaDiv = document.createElement('div');
        recaptchaDiv.id = 'recaptcha-container';
        container.appendChild(recaptchaDiv);

        document.body.appendChild(container);

        window.__challengeCallback = (token) => resolve(token);

        const script = document.createElement('script');
        script.src = 'https://www.google.com/recaptcha/api.js?onload=__onRecaptchaReady&render=explicit';
        script.async = true;

        window.__onRecaptchaReady = () => {
          grecaptcha.render('recaptcha-container', {
            sitekey: ${JSON.stringify(siteKey)},
            callback: (token) => window.__challengeCallback(token),
          });
        };

        document.head.appendChild(script);
      })
    `)

    sendCompletion(token)
    challengeWindow?.close()
  } catch {
    if (!completed) {
      sendCompletion(null)
      challengeWindow?.close()
    }
  }

  return { success: true }
}
