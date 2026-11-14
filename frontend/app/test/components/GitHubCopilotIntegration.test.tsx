import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { ProvidersTab } from "@/components/integrations/ProvidersTab"
import en from "@/i18n/locales/en.json"
import {
  ExternalIntegrationStatus,
  ExternalIntegrationType,
  type ExternalIntegration,
} from "@/types"

const {
  state,
  setupIntegration,
  pollIntegrationDevice,
  disableIntegration,
  openExternalAuthPage,
  copyToClipboard,
} = vi.hoisted(() => ({
  state: { app: {} as Record<string, unknown> },
  setupIntegration: vi.fn(),
  pollIntegrationDevice: vi.fn(),
  disableIntegration: vi.fn(),
  openExternalAuthPage: vi.fn(),
  copyToClipboard: vi.fn(),
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({ useAppContext: () => state.app }))
vi.mock("@/components/ai/AIModelsCard", () => ({ AIModelsCard: () => null }))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))
vi.mock("@/services/api", async importOriginal => ({
  ...(await importOriginal<typeof import("@/services/api")>()),
  setupIntegration,
  pollIntegrationDevice,
  disableIntegration,
}))
vi.mock("@/lib/externalAuth", async importOriginal => ({
  ...(await importOriginal<typeof import("@/lib/externalAuth")>()),
  openExternalAuthPage,
}))
vi.mock("@/lib/clipboard", () => ({ copyToClipboard }))

const NAME = "GitHub Copilot"
const VERIFICATION_URI = "https://github.com/login/device"
const POLL_TIMEOUT = { timeout: 4000 }
const device = en.settings.deviceAuthorization

const copilot = (
  overrides: Partial<ExternalIntegration> = {},
): ExternalIntegration => ({
  id: "GITHUB_COPILOT",
  name: NAME,
  type: ExternalIntegrationType.AI_PROVIDER,
  status: ExternalIntegrationStatus.OFF,
  available: true,
  payload_schema: {},
  ...overrides,
})

const renderTab = (integrations: ExternalIntegration[] = [copilot()]) => {
  state.app = {
    externalIntegrations: integrations,
    fetchExternalIntegrations: vi.fn(),
    showToast: vi.fn(),
  }
  render(
    <MemoryRouter initialEntries={["/entities?focus=GITHUB_COPILOT"]}>
      <ProvidersTab />
    </MemoryRouter>,
  )
}

const startAuthorization = async () => {
  fireEvent.click(await screen.findByRole("button", { name: en.common.setup }))
  await screen.findByText("ABCD-1234")
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, "error").mockImplementation(() => {})
  setupIntegration.mockResolvedValue({
    device: {
      flow_id: "flow",
      user_code: "ABCD-1234",
      verification_uri: VERIFICATION_URI,
      expires_in: 900,
      interval: 1,
    },
  })
  copyToClipboard.mockResolvedValue(true)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("GitHub Copilot device authorization", () => {
  it("connects with a one-time code", async () => {
    pollIntegrationDevice.mockResolvedValue({ status: "CONNECTED" })
    renderTab()

    expect(
      await screen.findByText(device.intro.replace("{integration}", NAME)),
    ).toBeInTheDocument()
    await startAuthorization()

    expect(setupIntegration).toHaveBeenCalledWith("GITHUB_COPILOT", {})
    expect(
      screen.getByText(device.instructions.replace("{site}", "github.com")),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: en.common.setup }),
    ).not.toBeInTheDocument()

    fireEvent.click(
      screen.getByRole("button", {
        name: device.copyAndOpen.replace("{site}", "github.com"),
      }),
    )
    expect(copyToClipboard).toHaveBeenCalledWith("ABCD-1234")
    expect(openExternalAuthPage).toHaveBeenCalledWith(VERIFICATION_URI)

    await waitFor(
      () =>
        expect(state.app.showToast).toHaveBeenCalledWith(
          en.settings.integrationEnabledSuccess.replace("{integration}", NAME),
          "success",
        ),
      POLL_TIMEOUT,
    )
    expect(pollIntegrationDevice).toHaveBeenCalledWith("GITHUB_COPILOT", "flow")
    expect(state.app.fetchExternalIntegrations).toHaveBeenCalledWith(true)
    expect(screen.queryByText("ABCD-1234")).not.toBeInTheDocument()
  })

  it("keeps polling while authorization is pending", async () => {
    pollIntegrationDevice
      .mockResolvedValueOnce({ status: "PENDING", interval: 1 })
      .mockResolvedValueOnce({ status: "CONNECTED" })
    renderTab()

    await startAuthorization()

    await waitFor(
      () => expect(pollIntegrationDevice).toHaveBeenCalledTimes(2),
      POLL_TIMEOUT,
    )
    await waitFor(() =>
      expect(state.app.fetchExternalIntegrations).toHaveBeenCalledWith(true),
    )
  })

  it("reports a denied authorization and allows retrying", async () => {
    pollIntegrationDevice.mockRejectedValue({ code: "AUTHORIZATION_DENIED" })
    renderTab()

    await startAuthorization()

    await waitFor(
      () =>
        expect(state.app.showToast).toHaveBeenCalledWith(
          en.errors.AUTHORIZATION_DENIED.replace("{integration}", NAME),
          "error",
        ),
      POLL_TIMEOUT,
    )
    expect(screen.queryByText("ABCD-1234")).not.toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: en.common.setup }),
    ).toBeInTheDocument()
  })

  it("stops polling when cancelled", async () => {
    renderTab()

    await startAuthorization()
    fireEvent.click(screen.getByRole("button", { name: en.common.cancel }))

    expect(screen.queryByText("ABCD-1234")).not.toBeInTheDocument()
    await new Promise(resolve => setTimeout(resolve, 1200))
    expect(pollIntegrationDevice).not.toHaveBeenCalled()
  })

  it("shows an unavailable method without allowing setup", () => {
    renderTab([copilot({ available: false })])

    expect(screen.getByText(NAME)).toBeInTheDocument()
    expect(
      screen.getByText(en.common.notAvailableOnPlatform),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: en.common.setup }),
    ).not.toBeInTheDocument()
  })
})
