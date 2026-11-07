import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { ProvidersTab } from "@/components/integrations/ProvidersTab"
import en from "@/i18n/locales/en.json"
import {
  ExternalIntegrationStatus,
  ExternalIntegrationType,
  PlatformType,
  type ExternalIntegration,
} from "@/types"

const {
  state,
  setupIntegration,
  completeIntegrationOAuth,
  disableIntegration,
  openExternalAuthPage,
  startLoopbackAuthorization,
} = vi.hoisted(() => ({
  state: { app: {} as Record<string, unknown> },
  setupIntegration: vi.fn(),
  completeIntegrationOAuth: vi.fn(),
  disableIntegration: vi.fn(),
  openExternalAuthPage: vi.fn(),
  startLoopbackAuthorization: vi.fn(),
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({ useAppContext: () => state.app }))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))
vi.mock("@/services/api", async importOriginal => ({
  ...(await importOriginal<typeof import("@/services/api")>()),
  setupIntegration,
  completeIntegrationOAuth,
  disableIntegration,
}))
vi.mock("@/lib/externalAuth", async importOriginal => ({
  ...(await importOriginal<typeof import("@/lib/externalAuth")>()),
  openExternalAuthPage,
  startLoopbackAuthorization,
}))

const NAME = "ChatGPT"
const LINK =
  "https://auth.openai.com/api/accounts/authorize?client_id=dynamic_agent_client&state=state-1"
const CALLBACK =
  "http://127.0.0.1:7592/auth/callback?code=code-1&state=state-1&client_id=oaiapp_1"
const copy = en.settings.chatgpt

const chatgpt = (
  overrides: Partial<ExternalIntegration> = {},
): ExternalIntegration => ({
  id: "CHATGPT",
  name: NAME,
  type: ExternalIntegrationType.AI_PROVIDER,
  status: ExternalIntegrationStatus.OFF,
  available: true,
  payload_schema: {},
  ...overrides,
})

const renderTab = (integration: ExternalIntegration = chatgpt()) => {
  state.app = {
    externalIntegrations: [integration],
    fetchExternalIntegrations: vi.fn(),
    showToast: vi.fn(),
  }
  render(
    <MemoryRouter initialEntries={["/entities?focus=CHATGPT"]}>
      <ProvidersTab />
    </MemoryRouter>,
  )
}

const continueWithChatGPT = async () => {
  fireEvent.click(await screen.findByRole("button", { name: copy.continue }))
}

const pasteAddress = async (address: string) => {
  fireEvent.change(await screen.findByPlaceholderText(copy.pastePlaceholder), {
    target: { value: address },
  })
  fireEvent.click(screen.getByRole("button", { name: copy.finish }))
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, "error").mockImplementation(() => {})
  setupIntegration.mockResolvedValue({ link: LINK })
  completeIntegrationOAuth.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  delete (window as { platform?: unknown }).platform
})

describe("ChatGPT sign-in", () => {
  it("shows only supported platforms as icon badges in a popover without toggling the card", async () => {
    renderTab(chatgpt({ platforms: ["DESKTOP", "SELF_HOSTED"] }))
    expect(
      screen.queryByText(en.settings.aiPlatformsLabel),
    ).not.toBeInTheDocument()
    const trigger = screen.getByRole("button", {
      name: en.settings.aiPlatformsLabel,
    })
    expect(trigger.textContent).toBe("")
    expect(trigger.querySelector("svg.lucide-info")).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole("button", { name: copy.continue })).toBeVisible(),
    )
    fireEvent.click(trigger)
    const popover = await screen.findByRole("dialog")
    expect(
      within(popover)
        .getByText(en.settings.aiPlatforms.DESKTOP)
        .querySelector("svg"),
    ).toBeInTheDocument()
    expect(
      within(popover)
        .getByText(en.settings.aiPlatforms.SELF_HOSTED)
        .querySelector("svg"),
    ).toBeInTheDocument()
    expect(
      within(popover).queryByText(en.settings.aiPlatforms.MOBILE),
    ).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: copy.continue })).toBeVisible()
    expect(setupIntegration).not.toHaveBeenCalled()
  })

  it.each([{ platforms: undefined }, { platforms: [] }])(
    "omits the platform trigger without supported-platform metadata",
    overrides => {
      renderTab(chatgpt(overrides))
      expect(
        screen.queryByRole("button", { name: en.settings.aiPlatformsLabel }),
      ).not.toBeInTheDocument()
    },
  )

  it("shows a beta badge on the integration card", () => {
    renderTab()

    expect(screen.getByText(en.settings.integrationBeta)).toBeInTheDocument()
  })

  it("groups OpenAI methods without sharing connection state", async () => {
    state.app = {
      externalIntegrations: [
        {
          id: "OPENAI",
          name: "OpenAI",
          family: { id: "OPENAI", name: "OpenAI" },
          platforms: ["DESKTOP", "SELF_HOSTED", "MOBILE"],
          type: ExternalIntegrationType.AI_PROVIDER,
          status: ExternalIntegrationStatus.ON,
          available: true,
          payload_schema: { api_key: "PASSWORD" },
        },
        chatgpt({
          family: { id: "OPENAI", name: "OpenAI" },
          platforms: ["DESKTOP", "SELF_HOSTED", "MOBILE"],
        }),
      ],
      fetchExternalIntegrations: vi.fn(),
      showToast: vi.fn(),
    }
    render(
      <MemoryRouter initialEntries={["/entities?focus=CHATGPT"]}>
        <ProvidersTab />
      </MemoryRouter>,
    )

    expect(screen.getByTestId("ai-family-OPENAI")).toBeInTheDocument()
    const focusedMethod = screen.getByTestId("integration-card-CHATGPT")
    expect(focusedMethod.parentElement).toHaveClass("px-3", "pb-3")
    expect(focusedMethod).toHaveClass(
      "rounded-md",
      "p-3",
      "ring-inset",
      "ring-1",
      "bg-accent/40",
    )
    expect(focusedMethod).not.toHaveClass("ring-2", "animate-pulse")
    expect(focusedMethod).toHaveClass("after:h-px", "last:after:hidden")
    expect(focusedMethod).not.toHaveClass("border-b")
    expect(screen.queryByText("1/2 connected")).not.toBeInTheDocument()
    for (const id of ["OPENAI", "CHATGPT"]) {
      const trigger = within(
        screen.getByTestId(`integration-card-${id}`),
      ).getByRole("button", { name: en.settings.aiPlatformsLabel })
      expect(trigger.textContent).toBe("")
      expect(trigger.querySelector("svg.lucide-info")).toBeInTheDocument()
    }
    expect(
      screen.getByText(en.settings.aiProviderMethods.OPENAI),
    ).toBeInTheDocument()
    expect(
      screen.getByText(en.settings.aiProviderMethods.CHATGPT),
    ).toBeInTheDocument()
    await continueWithChatGPT()
    expect(setupIntegration).toHaveBeenCalledWith(
      "CHATGPT",
      {},
      expect.any(String),
    )
    expect(disableIntegration).not.toHaveBeenCalled()
  })

  it("renders an unknown backend family and its methods without a frontend registry", () => {
    state.app = {
      externalIntegrations: ["FUTURE_API", "FUTURE_PLAN"].map(id => ({
        id,
        name: id === "FUTURE_API" ? "Future API" : "Future Plan",
        family: { id: "FUTURE_FAMILY", name: "Future Service" },
        type: ExternalIntegrationType.AI_PROVIDER,
        status: ExternalIntegrationStatus.OFF,
        available: true,
        payload_schema: {},
      })),
      fetchExternalIntegrations: vi.fn(),
      showToast: vi.fn(),
    }
    render(
      <MemoryRouter initialEntries={["/entities?focus=FUTURE_PLAN"]}>
        <ProvidersTab />
      </MemoryRouter>,
    )
    expect(screen.getByTestId("ai-family-FUTURE_FAMILY")).toHaveTextContent(
      "Future Service",
    )
    expect(screen.getByTestId("integration-card-FUTURE_API")).toHaveTextContent(
      "Future API",
    )
    expect(
      screen.getByTestId("integration-card-FUTURE_PLAN"),
    ).toHaveTextContent("Future Plan")
    expect(
      screen.getByRole("button", { name: en.common.setup }),
    ).toBeInTheDocument()
  })

  it("opens the sign-in page and completes from the pasted address", async () => {
    renderTab()

    await continueWithChatGPT()

    await waitFor(() => expect(openExternalAuthPage).toHaveBeenCalledWith(LINK))
    expect(setupIntegration).toHaveBeenCalledWith(
      "CHATGPT",
      {},
      expect.stringContaining("integration_oauth=CHATGPT"),
    )
    expect(
      screen.getByText(en.settings.integrationAwaitingAuthorization),
    ).toBeInTheDocument()

    await pasteAddress(CALLBACK)

    await waitFor(() =>
      expect(completeIntegrationOAuth).toHaveBeenCalledWith("CHATGPT", {
        state: "state-1",
        code: "code-1",
        error: null,
        client_id: "oaiapp_1",
      }),
    )
    await waitFor(() =>
      expect(state.app.showToast).toHaveBeenCalledWith(
        en.settings.integrationEnabledSuccess.replace("{integration}", NAME),
        "success",
      ),
    )
    expect(
      screen.queryByPlaceholderText(copy.pastePlaceholder),
    ).not.toBeInTheDocument()
  })

  it("authorizes once more when ChatGPT asks for another sign-in", async () => {
    completeIntegrationOAuth.mockRejectedValue({
      code: "AUTHORIZATION_RETRY_REQUIRED",
    })
    renderTab()
    await continueWithChatGPT()

    await pasteAddress(CALLBACK)

    await waitFor(() => expect(openExternalAuthPage).toHaveBeenCalledTimes(2))
    expect(setupIntegration).toHaveBeenCalledTimes(2)
    expect(state.app.showToast).not.toHaveBeenCalled()

    await pasteAddress(CALLBACK)

    await waitFor(() =>
      expect(state.app.showToast).toHaveBeenCalledWith(
        en.errors.AUTHORIZATION_RETRY_REQUIRED.replace("{integration}", NAME),
        "error",
      ),
    )
    expect(setupIntegration).toHaveBeenCalledTimes(2)
  })

  it("rejects an address without a sign-in response", async () => {
    renderTab()
    await continueWithChatGPT()

    await pasteAddress("https://chatgpt.com/")

    expect(state.app.showToast).toHaveBeenCalledWith(
      copy.invalidAddress,
      "error",
      { reportable: false },
    )
    expect(completeIntegrationOAuth).not.toHaveBeenCalled()
  })

  it("stops waiting when cancelled", async () => {
    renderTab()
    await continueWithChatGPT()
    await screen.findByPlaceholderText(copy.pastePlaceholder)

    fireEvent.click(screen.getByRole("button", { name: en.common.cancel }))

    expect(
      screen.queryByPlaceholderText(copy.pastePlaceholder),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: copy.continue }),
    ).toBeInTheDocument()
  })

  it("receives the redirect through the app listener on mobile", async () => {
    window.platform = { type: PlatformType.IOS } as typeof window.platform
    const wait = vi.fn().mockResolvedValue({
      integrationId: "CHATGPT",
      state: "state-1",
      code: "code-1",
      error: null,
      clientId: "oaiapp_1",
    })
    startLoopbackAuthorization.mockResolvedValue({
      callbackUrl: "http://127.0.0.1:53123/auth/callback",
      wait,
      cancel: vi.fn(),
    })
    renderTab()

    await continueWithChatGPT()

    await waitFor(() =>
      expect(completeIntegrationOAuth).toHaveBeenCalledWith("CHATGPT", {
        state: "state-1",
        code: "code-1",
        error: null,
        client_id: "oaiapp_1",
      }),
    )
    expect(setupIntegration).toHaveBeenCalledWith(
      "CHATGPT",
      {},
      "http://127.0.0.1:53123/auth/callback",
    )
    expect(wait).toHaveBeenCalledWith(LINK)
    expect(openExternalAuthPage).not.toHaveBeenCalled()
  })

  it("stops the app listener when the setup fails on mobile", async () => {
    window.platform = { type: PlatformType.ANDROID } as typeof window.platform
    const cancel = vi.fn()
    startLoopbackAuthorization.mockResolvedValue({
      callbackUrl: "http://127.0.0.1:53123/auth/callback",
      wait: vi.fn(),
      cancel,
    })
    setupIntegration.mockRejectedValue({ code: "UNKNOWN" })
    renderTab()

    await continueWithChatGPT()

    await waitFor(() => expect(cancel).toHaveBeenCalled())
  })

  it("shows the plan usage link when connected", async () => {
    renderTab(chatgpt({ status: ExternalIntegrationStatus.ON }))

    expect(await screen.findByText(copy.usingPlan)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: copy.manageUsage }))

    expect(openExternalAuthPage).toHaveBeenCalledWith(
      "https://chatgpt.com/settings/usage",
    )
    expect(
      screen.queryByRole("button", { name: copy.continue }),
    ).not.toBeInTheDocument()
  })

  it("offers to sign in again when the sign-in expired", async () => {
    renderTab(chatgpt({ status: ExternalIntegrationStatus.EXPIRED }))

    expect(await screen.findByText(copy.expired)).toBeInTheDocument()
    expect(
      screen.getAllByText(en.settings.integrationExpired).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getByRole("button", { name: copy.continue }),
    ).toBeInTheDocument()
    expect(screen.getByText(en.entities.disconnect)).toBeInTheDocument()
  })
})
