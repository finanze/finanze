let wafIframe: HTMLIFrameElement | null = null

interface WafIntegration {
  getToken: () => Promise<string>
}

function getIntegration(): WafIntegration | undefined {
  return (
    wafIframe?.contentWindow as Window & { AwsWafIntegration?: WafIntegration }
  )?.AwsWafIntegration
}

export async function resolveAwsWafToken(scriptUrl: string): Promise<string> {
  const existing = getIntegration()
  if (existing) {
    return existing.getToken()
  }

  return new Promise((resolve, reject) => {
    const iframe = document.createElement("iframe")
    iframe.style.display = "none"
    iframe.setAttribute("aria-hidden", "true")
    document.body.appendChild(iframe)

    const doc = iframe.contentDocument
    if (!doc) {
      iframe.remove()
      reject(new Error("Failed to create iframe document"))
      return
    }

    const script = doc.createElement("script")
    script.src = scriptUrl
    script.onload = async () => {
      wafIframe = iframe
      const integration = getIntegration()
      if (!integration) {
        iframe.remove()
        wafIframe = null
        reject(new Error("AwsWafIntegration not available after load"))
        return
      }
      try {
        resolve(await integration.getToken())
      } catch (e) {
        reject(e)
      }
    }
    script.onerror = () => {
      iframe.remove()
      reject(new Error("Failed to load AWS WAF challenge script"))
    }
    doc.head.appendChild(script)
  })
}

export async function getFreshAwsWafToken(): Promise<string | undefined> {
  const integration = getIntegration()
  if (!integration) return undefined
  try {
    return await integration.getToken()
  } catch {
    return undefined
  }
}

export function cleanupAwsWaf(): void {
  if (wafIframe) {
    wafIframe.remove()
    wafIframe = null
  }
}
