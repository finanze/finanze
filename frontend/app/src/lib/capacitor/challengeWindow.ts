import { LoginWebView } from "./loginWebView"

type ChallengeCallback = (token: string | null) => void
let challengeCallback: ChallengeCallback | null = null

export function onChallengeCompleted(callback: ChallengeCallback): () => void {
  challengeCallback = callback
  return () => {
    challengeCallback = null
  }
}

function emitChallengeCompletion(token: string | null) {
  const cb = challengeCallback
  if (cb) {
    setTimeout(() => {
      try {
        cb(token)
      } catch (err) {
        console.error("[ChallengeWindow] callback error:", err)
      }
    }, 0)
  }
}

export async function requestChallengeWindow(
  siteKey: string,
  domain: string,
): Promise<{ success: boolean }> {
  let completed = false

  function sendCompletion(token: string | null) {
    if (completed) return
    completed = true
    emitChallengeCompletion(token)
    LoginWebView.removeAllListeners()
  }

  try {
    await LoginWebView.addListener(
      "requestIntercepted",
      (data: { url: string }) => {
        if (data.url.startsWith("finanze://challenge-token")) {
          try {
            const url = new URL(data.url)
            const token = url.searchParams.get("token")
            if (token) {
              sendCompletion(token)
              LoginWebView.close()
            }
          } catch {
            // ignore parse errors
          }
        }
      },
    )

    await LoginWebView.addListener("pageLoaded", async () => {
      try {
        await LoginWebView.executeScript({
          code: `
            (function() {
              document.body.innerHTML = '';
              document.body.style.cssText = 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f5f5f5;font-family:system-ui,sans-serif;';

              var container = document.createElement('div');
              container.style.cssText = 'text-align:center;';

              var title = document.createElement('p');
              title.textContent = 'Complete the security challenge';
              title.style.cssText = 'margin-bottom:20px;font-size:16px;color:#333;';
              container.appendChild(title);

              var recaptchaDiv = document.createElement('div');
              recaptchaDiv.id = 'recaptcha-container';
              container.appendChild(recaptchaDiv);

              document.body.appendChild(container);

              window.__onRecaptchaReady = function() {
                grecaptcha.render('recaptcha-container', {
                  sitekey: ${JSON.stringify(siteKey)},
                  callback: function(token) {
                    window.location.href = 'finanze://challenge-token?token=' + encodeURIComponent(token);
                  },
                });
              };

              var script = document.createElement('script');
              script.src = 'https://www.google.com/recaptcha/api.js?onload=__onRecaptchaReady&render=explicit';
              script.async = true;
              document.head.appendChild(script);
            })();
          `,
        })
      } catch {
        // ignore script injection errors
      }
    })

    await LoginWebView.addListener("closed", () => {
      if (!completed) {
        sendCompletion(null)
      }
    })

    await LoginWebView.open({
      url: `https://${domain}`,
      title: "Security Challenge",
      clearSession: false,
      interceptUrlPatterns: ["finanze://challenge-token"],
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to open challenge window:", error)
    return { success: false }
  }
}
