import { isNativeMobile } from "@/lib/platform"

export interface ChallengeWindowAPI {
  requestChallengeWindow(
    siteKey: string,
    domain: string,
  ): Promise<{ success: boolean }>
  onChallengeCompleted(callback: (token: string | null) => void): () => void
}

let mobileChallengeAPI: ChallengeWindowAPI | null = null

export function getChallengeWindowAPI(): ChallengeWindowAPI | null {
  if (typeof window !== "undefined" && window.ipcAPI) {
    return {
      requestChallengeWindow: (siteKey, domain) =>
        window.ipcAPI!.requestChallengeWindow(siteKey, domain),
      onChallengeCompleted: callback => {
        return window.ipcAPI!.onChallengeCompleted(callback)
      },
    }
  }

  if (isNativeMobile() || mobileChallengeAPI) {
    return mobileChallengeAPI
  }

  return null
}

export function setMobileChallengeAPI(api: ChallengeWindowAPI | null) {
  mobileChallengeAPI = api
}
