import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { AIImportSettingsCard } from "@/components/import/AIImportSettingsCard"
import { ExternalIntegrationStatus, ExternalIntegrationType } from "@/types"
import { AITask } from "@/types/ai"
import en from "@/i18n/locales/en.json"

const { getAIProviders, getAIModels, navigate, appContext } = vi.hoisted(
  () => ({
    getAIProviders: vi.fn(),
    getAIModels: vi.fn(),
    navigate: vi.fn(),
    appContext: { current: {} as Record<string, unknown> },
  }),
)

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => appContext.current,
}))
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }))
vi.mock("@/services/api", () => ({
  getAIProviders,
  getAIModels,
  validateAIModel: vi.fn(),
  getLocalModels: vi.fn(),
  getApiServerInfo: vi.fn().mockResolvedValue({ isCustomServer: false }),
}))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))

const copy = en.export.fileImport.ai.settings
const SHEETS = { globals: {} }

const renderCard = (ai = { providers: [], instructions: null }) => {
  appContext.current = {
    settings: {
      ai: { providers: [{ provider: "OPENAI", model: "gpt-6-luna" }] },
      importing: { sheets: SHEETS, ai },
    },
    saveSettings: vi.fn().mockResolvedValue(true),
    externalIntegrations: [
      {
        id: "OPENROUTER",
        name: "OpenRouter",
        type: ExternalIntegrationType.AI_PROVIDER,
        status: ExternalIntegrationStatus.ON,
        available: true,
      },
    ],
    fetchExternalIntegrations: vi.fn(),
  }
  getAIProviders.mockResolvedValue({
    providers: [
      {
        id: "OPENROUTER",
        connected: true,
        recommended_models: [
          { id: "vision-model", name: "Vision", probabilistic: false },
        ],
        custom_models: true,
        upstream_providers: false,
      },
    ],
  })
  render(<AIImportSettingsCard />)
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("AIImportSettingsCard", () => {
  it("expands to show the default models and saves import notes", async () => {
    renderCard()

    expect(screen.getByText(copy.title)).toBeInTheDocument()
    expect(screen.queryByTestId("import-ai-editor")).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId("import-ai-settings-toggle"))
    expect(await screen.findByTestId("import-ai-priority-0")).toHaveTextContent(
      "gpt-6-luna",
    )
    expect(screen.getByTestId("import-ai-editor")).toHaveAttribute(
      "aria-disabled",
      "true",
    )
    expect(screen.queryByTestId("import-ai-save")).not.toBeInTheDocument()
    expect(
      screen.queryByLabelText(copy.instructionsLabel),
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId("import-ai-instructions-toggle"))
    fireEvent.change(screen.getByLabelText(copy.instructionsLabel), {
      target: { value: "  Amounts are in USD  " },
    })
    fireEvent.click(screen.getByTestId("import-ai-save"))

    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        importing: {
          sheets: SHEETS,
          ai: { providers: [], instructions: "Amounts are in USD" },
        },
      }),
    )
  })

  it("saves a custom model list for imports", async () => {
    renderCard()

    fireEvent.click(screen.getByTestId("import-ai-settings-toggle"))
    fireEvent.click(await screen.findByTestId("import-ai-custom-toggle"))
    await waitFor(() =>
      expect(getAIProviders).toHaveBeenCalledWith(AITask.IMPORTING),
    )
    fireEvent.click(await screen.findByTestId("import-ai-save"))

    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        importing: {
          sheets: SHEETS,
          ai: {
            providers: [
              {
                provider: "OPENAI",
                model: "gpt-6-luna",
                upstreamProvider: null,
              },
            ],
            instructions: null,
          },
        },
      }),
    )
  })
})
