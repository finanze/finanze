import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import EntityIntegrationsPage from "@/pages/EntityIntegrationsPage"
import SettingsPage from "@/pages/SettingsPage"
import en from "@/i18n/locales/en.json"
import { FFStatus, PlatformType } from "@/types"

const { state, setupIntegration, disableIntegration } = vi.hoisted(() => ({
  state: {
    app: {} as Record<string, unknown>,
    native: false,
  },
  setupIntegration: vi.fn(),
  disableIntegration: vi.fn(),
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({ useAppContext: () => state.app }))
vi.mock("@/context/EntityWorkflowContext", () => ({
  useEntityWorkflow: () => ({ view: "entities", selectedEntity: null }),
}))
vi.mock("@/components/ExternalEntityConnection", () => ({
  ENABLE_BANKING_PROVIDER: "ENABLE_BANKING",
  useExternalEntityConnection: () => ({ hasAvailableEntityProvider: true }),
  ExternalEntityConnectionModals: () => null,
}))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))
vi.mock("@/context/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", setThemeMode: vi.fn() }),
}))
vi.mock("@/context/CloudContext", () => ({ useCloud: () => ({ role: null }) }))
vi.mock("@/context/BackupAlertContext", () => ({
  useBackupAlert: () => ({ alertColor: null }),
}))
vi.mock("@/context/DataDisplayModeContext", () => ({
  useDataDisplayMode: () => ({ mode: "normal", setMode: vi.fn() }),
}))
vi.mock("@/components/settings/GeneralTab", () => ({ GeneralTab: () => null }))
vi.mock("@/components/settings/CloudTab", () => ({ CloudTab: () => null }))
vi.mock("@/components/settings/McpTab", () => ({ McpTab: () => null }))
vi.mock("@/lib/platform", async importOriginal => ({
  ...(await importOriginal<typeof import("@/lib/platform")>()),
  isNativeMobile: () => state.native,
  getPlatformType: () => PlatformType.WEB,
}))
vi.mock("@/services/api", async importOriginal => ({
  ...(await importOriginal<typeof import("@/services/api")>()),
  setupIntegration,
  disableIntegration,
}))

function LocationProbe() {
  const location = useLocation()
  return (
    <output data-testid="location">
      {location.pathname + location.search}
    </output>
  )
}

function renderRoute(route = "/entities") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <LocationProbe />
      <Routes>
        <Route path="/entities" element={<EntityIntegrationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(window, "scrollTo").mockImplementation(() => {})
  state.native = false
  state.app = {
    entities: [],
    isLoadingEntities: false,
    fetchEntities: vi.fn(),
    externalIntegrations: [
      {
        id: "OPENAI",
        name: "OpenAI",
        type: "AI_PROVIDER",
        status: "OFF",
        available: true,
        payload_schema: { api_key: "API Key" },
      },
    ],
    fetchExternalIntegrations: vi.fn(),
    showToast: vi.fn(),
    fetchSettings: vi.fn(),
    isLoadingSettings: false,
    featureFlags: { CLOUD: FFStatus.OFF },
  }
  setupIntegration.mockResolvedValue(undefined)
  disableIntegration.mockResolvedValue(undefined)
})

afterEach(cleanup)

describe("Integration tabs", () => {
  it.each(["/entities", "/entities?tab=entities", "/entities?tab=unknown"])(
    "defaults to entities at %s",
    async route => {
      renderRoute(route)
      expect(
        screen.getByRole("tab", { name: en.entities.tabEntities }),
      ).toHaveAttribute("aria-selected", "true")
      await waitFor(() =>
        expect(
          screen.getByRole("tabpanel", { name: en.entities.tabEntities }),
        ).toBeVisible(),
      )
      expect(screen.queryByText("OpenAI")).not.toBeInTheDocument()
    },
  )

  it("opens providers directly and expands the focused provider", async () => {
    renderRoute("/entities?tab=providers&focus=OPENAI")
    expect(
      screen.getByRole("tab", { name: en.entities.tabProviders }),
    ).toHaveAttribute("aria-selected", "true")
    expect(
      screen.queryByRole("tabpanel", { name: en.entities.tabEntities }),
    ).not.toBeInTheDocument()
    expect(await screen.findByLabelText("API Key")).toBeVisible()
    expect(screen.getByText("OpenAI").closest(".ring-2")).not.toBeNull()
  })

  it("retains provider drafts and entity categories across tab switches", async () => {
    renderRoute()
    fireEvent.click(
      screen.getByRole("button", { name: en.entities.financialInstitutions }),
    )
    fireEvent.click(screen.getByRole("tab", { name: en.entities.tabProviders }))
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/entities?tab=providers",
    )
    fireEvent.click(await screen.findByText("OpenAI"))
    fireEvent.change(await screen.findByLabelText("API Key"), {
      target: { value: "draft-key" },
    })
    fireEvent.click(screen.getByRole("tab", { name: en.entities.tabEntities }))
    expect(
      screen.getByRole("button", { name: en.entities.financialInstitutions }),
    ).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByLabelText("API Key")).not.toBeVisible()
    fireEvent.click(screen.getByRole("tab", { name: en.entities.tabProviders }))
    expect(screen.getByLabelText("API Key")).toHaveValue("draft-key")
    expect(state.app.fetchExternalIntegrations).not.toHaveBeenCalled()
  })

  it("routes entity-provider setup to the providers tab", async () => {
    renderRoute()
    fireEvent.click(screen.getByText(en.entities.moreFinancialInstitutionsCard))
    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/entities?tab=providers&focus=ENABLE_BANKING",
      ),
    )
    expect(
      screen.getByRole("tab", { name: en.entities.tabProviders }),
    ).toHaveAttribute("aria-selected", "true")
  })

  it("keeps provider setup and disable actions working", async () => {
    state.app.externalIntegrations = [
      {
        id: "OPENAI",
        name: "OpenAI",
        type: "AI_PROVIDER",
        status: "ON",
        available: true,
        payload_schema: { api_key: "API Key" },
      },
    ]
    renderRoute("/entities?tab=providers&focus=OPENAI")
    fireEvent.change(await screen.findByLabelText("API Key"), {
      target: { value: " replacement-key " },
    })
    fireEvent.click(screen.getByRole("button", { name: en.common.setup }))
    await waitFor(() =>
      expect(setupIntegration).toHaveBeenCalledWith("OPENAI", {
        api_key: "replacement-key",
      }),
    )
    await waitFor(() =>
      expect(state.app.fetchExternalIntegrations).toHaveBeenCalledWith(true),
    )
    fireEvent.click(
      screen.getByRole("button", { name: en.entities.disconnect }),
    )
    await waitFor(() =>
      expect(disableIntegration).toHaveBeenCalledWith("OPENAI"),
    )
  })
})

describe("Settings integration migration", () => {
  it.each(["", "&focus=OPENAI"])(
    "redirects legacy integration links%s",
    async suffix => {
      state.app.isLoadingSettings = true
      renderRoute(`/settings?tab=integrations${suffix}`)
      await waitFor(() =>
        expect(screen.getByTestId("location")).toHaveTextContent(
          `/entities?tab=providers${suffix}`,
        ),
      )
      expect(
        screen.getByRole("tab", { name: en.entities.tabProviders }),
      ).toHaveAttribute("aria-selected", "true")
      if (suffix) expect(await screen.findByLabelText("API Key")).toBeVisible()
    },
  )

  it.each([
    { native: true, cloud: false, count: 2 },
    { native: true, cloud: true, count: 3 },
    { native: false, cloud: false, count: 3 },
    { native: false, cloud: true, count: 4 },
  ])(
    "keeps $count settings tabs with native=$native and cloud=$cloud",
    ({ native, cloud, count }) => {
      state.native = native
      state.app.featureFlags = { CLOUD: cloud ? FFStatus.ON : FFStatus.OFF }
      renderRoute("/settings")
      expect(screen.getAllByRole("tab")).toHaveLength(count)
      expect(screen.getByRole("tablist")).toHaveClass(`sm:grid-cols-${count}`)
      expect(
        screen.queryByRole("tab", { name: en.settings.integrations }),
      ).not.toBeInTheDocument()
      expect(
        screen.getByRole("tab", { name: en.settings.general }),
      ).toHaveAttribute("aria-selected", "true")
    },
  )
})
