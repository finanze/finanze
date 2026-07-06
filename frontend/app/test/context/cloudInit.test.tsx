import { describe, it, expect, beforeEach, vi } from "vitest"
import { render, waitFor, cleanup } from "@testing-library/react"
import { FFStatus } from "@/types"
import { CloudProvider, useCloud } from "@/context/CloudContext"

let currentIsAuthenticated = false
let currentFeatureFlags: Record<string, FFStatus> = {}

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ isAuthenticated: currentIsAuthenticated }),
}))

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({ featureFlags: currentFeatureFlags }),
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({ t: { settings: { cloud: { oauthErrors: {} } } } }),
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}))

vi.mock("@/hooks/useBackupStatus", () => ({
  resetBackupStatusCache: vi.fn(),
}))

const mockProvider = {
  initialize: vi.fn().mockResolvedValue(undefined),
  getSession: vi.fn().mockResolvedValue(null),
  setSession: vi.fn().mockResolvedValue(undefined),
  clearLocalSession: vi.fn().mockResolvedValue(undefined),
  setAutoRefreshEnabled: vi.fn().mockResolvedValue(undefined),
  onAuthStateChange: vi.fn().mockReturnValue(() => {}),
  handleAuthCallbackUrl: vi.fn().mockResolvedValue(undefined),
}

vi.mock("@/services/cloud", () => ({
  SupabaseAuthProvider: vi.fn().mockImplementation(() => mockProvider),
}))

vi.mock("@/services/api", () => ({
  cloudAuth: vi.fn().mockResolvedValue(undefined),
  getCloudAuthToken: vi.fn().mockResolvedValue(null),
  getApiServerInfo: vi.fn().mockResolvedValue({}),
  getBackupSettings: vi.fn().mockResolvedValue({ mode: "OFF" }),
  updateBackupSettings: vi.fn().mockResolvedValue(undefined),
}))

vi.mock("@/lib/platform", () => ({
  isNativeMobile: () => false,
  isElectron: () => false,
}))

vi.mock("@/lib/mobile/socialLogin", () => ({
  signInWithGoogleMobile: vi.fn(),
  signInWithAppleMobile: vi.fn(),
}))

let observed: { isInitialized: boolean } = { isInitialized: false }

function Probe() {
  const { isInitialized } = useCloud()
  observed = { isInitialized }
  return null
}

function renderCloud() {
  return render(
    <CloudProvider>
      <Probe />
    </CloudProvider>,
  )
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  currentIsAuthenticated = false
  currentFeatureFlags = {}
  observed = { isInitialized: false }
})

describe("CloudContext initialization gating", () => {
  it("stays uninitialized while unauthenticated even with empty feature flags", async () => {
    currentIsAuthenticated = false
    currentFeatureFlags = {}

    renderCloud()

    // Give effects a chance to run
    await waitFor(() => {
      expect(observed).toBeDefined()
    })

    expect(observed.isInitialized).toBe(false)
  })

  it("marks initialized once authenticated with cloud disabled", async () => {
    currentIsAuthenticated = true
    currentFeatureFlags = { CLOUD: FFStatus.OFF }

    renderCloud()

    await waitFor(() => {
      expect(observed.isInitialized).toBe(true)
    })
  })
})
