import { setMobileChallengeAPI } from "@/lib/challengeWindow"
import type { ChallengeWindowAPI } from "@/lib/challengeWindow"

export function initE2eMockChallengeWindow() {
  if (!import.meta.env.DEV) return
  if (!import.meta.env.VITE_E2E_MOCK_LOGIN) return

  let completionCallback: ((token: string | null) => void) | null = null

  const mockAPI: ChallengeWindowAPI = {
    requestChallengeWindow: () => {
      setTimeout(() => {
        completionCallback?.("mock-challenge-token")
      }, 500)

      return Promise.resolve({ success: true })
    },

    onChallengeCompleted: callback => {
      completionCallback = callback
      return () => {
        completionCallback = null
      }
    },
  }

  setMobileChallengeAPI(mockAPI)
  ;(window as any).__e2eDisableMockChallengeWindow = () => {
    setMobileChallengeAPI(null)
  }
  ;(window as any).__e2eEnableMockChallengeWindow = () => {
    setMobileChallengeAPI(mockAPI)
  }

  console.log("[Dev] E2E mock challenge window API registered")
}
