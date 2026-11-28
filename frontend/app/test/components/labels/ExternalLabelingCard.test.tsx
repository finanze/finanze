import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { ExternalLabelingCard } from "@/components/labels/ExternalLabelingCard"
import {
  AIInputModality,
  LocalModelSource,
  LocalModelState,
  LocalRuntimeMode,
  LocalRuntimeSource,
  type AIProviderDetails,
  type LocalModel,
  type LocalModelsOverview,
} from "@/types/ai"
import { LabelOrigin } from "@/types/transactions"
import { ExternalIntegrationStatus, ExternalIntegrationType } from "@/types"
import type { ExternalLabelingSettings } from "@/types/labeling"
import en from "@/i18n/locales/en.json"
import es from "@/i18n/locales/es.json"
import itTranslations from "@/i18n/locales/it.json"

const {
  getExternalLabelingProviders,
  getExternalLabelingModels,
  validateAIModel,
  getLocalModels,
  downloadLocalModel,
  deleteLocalModel,
  importLocalModel,
  getHuggingFaceQuants,
  getApiServerInfo,
  navigate,
  appContext,
} = vi.hoisted(() => ({
  getExternalLabelingProviders: vi.fn(),
  getExternalLabelingModels: vi.fn(),
  validateAIModel: vi.fn(),
  getLocalModels: vi.fn(),
  downloadLocalModel: vi.fn(),
  deleteLocalModel: vi.fn(),
  importLocalModel: vi.fn(),
  getHuggingFaceQuants: vi.fn(),
  getApiServerInfo: vi.fn(),
  navigate: vi.fn(),
  appContext: {
    current: {} as Record<string, unknown>,
    locale: "en-US" as "en-US" | "es-ES" | "it-IT",
  },
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({
    t:
      appContext.locale === "es-ES"
        ? es
        : appContext.locale === "it-IT"
          ? itTranslations
          : en,
    locale: appContext.locale,
  }),
}))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => appContext.current,
}))
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }))
vi.mock("@/services/api", () => ({
  getAIProviders: getExternalLabelingProviders,
  getAIModels: getExternalLabelingModels,
  validateAIModel,
  getLocalModels,
  downloadLocalModel,
  deleteLocalModel,
  importLocalModel,
  getHuggingFaceQuants,
  getApiServerInfo,
}))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))

const external = en.labels.external
const localCopy = en.settings.localModels

const LOCAL_PROVIDER: AIProviderDetails = {
  id: "LOCAL_MODELS",
  connected: true,
  recommended_models: [],
  custom_models: false,
  upstream_providers: false,
  dynamic_models: true,
}

const COMPATIBLE_PROVIDER: AIProviderDetails = {
  id: "OPENAI_COMPATIBLE",
  connected: true,
  recommended_models: [],
  custom_models: true,
  upstream_providers: false,
  dynamic_models: true,
}

const COPILOT_PROVIDER: AIProviderDetails = {
  id: "GITHUB_COPILOT",
  connected: true,
  recommended_models: [],
  custom_models: false,
  upstream_providers: false,
  dynamic_models: true,
}

const settings = (provider: string, model: string | null = null) => {
  const externalSettings: ExternalLabelingSettings = {
    enabled: true,
    providers: [{ provider, model: model ?? "", upstreamProvider: null }],
    autoRun: false,
    minConfidence: 0.5,
    maxPerRun: 100,
    examples: { enabled: false, count: 10, origins: [LabelOrigin.MANUAL] },
    instructions: null,
  }
  return { labeling: { external: externalSettings } }
}

const localModel = (overrides: Partial<LocalModel>): LocalModel => ({
  id: "org/model-GGUF:Q4_K_M",
  name: "Model",
  source: LocalModelSource.HUGGING_FACE,
  state: LocalModelState.UNLOADED,
  decisions: false,
  deletable: true,
  size: 1_000_000,
  ...overrides,
})

const overview = (models: LocalModel[]): LocalModelsOverview => ({
  connected: true,
  capabilities: {
    built_in_available: true,
    can_import_files: true,
    env_api_key_set: false,
  },
  catalog: [],
  mode: LocalRuntimeMode.BUILT_IN,
  source: LocalRuntimeSource.BUILT_IN,
  reachable: true,
  models,
})

const renderCard = (
  provider: AIProviderDetails,
  model: string | null = null,
) => {
  appContext.current = {
    settings: settings(provider.id, model),
    saveSettings: vi.fn(),
    externalIntegrations: [],
    fetchExternalIntegrations: vi.fn(),
    showToast: vi.fn(),
  }
  getExternalLabelingProviders.mockResolvedValue({ providers: [provider] })
  render(<ExternalLabelingCard />)
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  appContext.locale = "en-US"
  getApiServerInfo.mockResolvedValue({ isCustomServer: false })
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe("ExternalLabelingCard models", () => {
  it("updates family and method labels on language changes while preserving provider and model", async () => {
    appContext.locale = "es-ES"
    appContext.current = {
      settings: settings("OPENAI_COMPATIBLE", "locale-model"),
      saveSettings: vi.fn(),
      externalIntegrations: [
        {
          id: "OPENAI_COMPATIBLE",
          name: "Database name",
          family: { id: "CUSTOM", name: "Custom AI" },
          type: ExternalIntegrationType.AI_PROVIDER,
          status: ExternalIntegrationStatus.ON,
          available: true,
        },
      ],
      fetchExternalIntegrations: vi.fn(),
      showToast: vi.fn(),
    }
    getExternalLabelingProviders.mockResolvedValue({
      providers: [
        {
          ...COMPATIBLE_PROVIDER,
          dynamic_models: false,
          recommended_models: [
            { id: "locale-model", name: "locale-model", probabilistic: false },
          ],
        },
      ],
    })
    const view = render(<ExternalLabelingCard />)
    const row = await screen.findByTestId("external-priority-0")
    expect(row).toHaveTextContent("IA personalizada - API compatible")
    expect(row).toHaveTextContent("locale-model")
    const fetchCalls = (
      appContext.current.fetchExternalIntegrations as ReturnType<typeof vi.fn>
    ).mock.calls.length
    appContext.locale = "it-IT"
    view.rerender(<ExternalLabelingCard />)
    expect(row).toHaveTextContent("IA personalizzata - API compatibile")
    expect(row).toHaveTextContent("locale-model")
    expect(appContext.current.fetchExternalIntegrations).toHaveBeenCalledTimes(
      fetchCalls,
    )
    fireEvent.click(
      screen.getByRole("button", {
        name: itTranslations.labels.external.moreSettings,
      }),
    )
    const switches = screen.getAllByRole("switch")
    expect(switches[1]).toHaveAttribute("id", "external-custom-toggle")
    fireEvent.click(switches[2])
    fireEvent.click(
      screen.getByRole("button", { name: itTranslations.common.save }),
    )
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: {
          external: expect.objectContaining({
            providers: [
              {
                provider: "OPENAI_COMPATIBLE",
                model: "locale-model",
                upstreamProvider: null,
              },
            ],
          }),
        },
      }),
    )
  })

  const priorityModels = [
    { id: "OPENROUTER", model: "router-model" },
    { id: "CHATGPT", model: "chat-model" },
    { id: "OPENAI", model: "api-model" },
  ]
  const renderPriorities = (ids = ["OPENROUTER"]) => {
    const configured = settings("OPENROUTER", "router-model")
    configured.labeling.external.providers = ids.map(id => ({
      provider: id,
      model:
        priorityModels.find(item => item.id === id)?.model ?? "claude-model",
      upstreamProvider: null,
    }))
    appContext.current = {
      settings: configured,
      saveSettings: vi.fn(),
      externalIntegrations: [
        ...priorityModels.map(item => ({
          id: item.id,
          name: item.id,
          type: ExternalIntegrationType.AI_PROVIDER,
          status: ExternalIntegrationStatus.ON,
          available: true,
        })),
        {
          id: "CLAUDE_AGENT",
          name: "Claude",
          type: ExternalIntegrationType.AI_PROVIDER,
          status: ExternalIntegrationStatus.ON,
          available: false,
        },
      ],
      fetchExternalIntegrations: vi.fn(),
    }
    getExternalLabelingProviders.mockResolvedValue({
      providers: priorityModels.map(item => ({
        id: item.id,
        connected: true,
        recommended_models: [
          { id: item.model, name: item.model, probabilistic: false },
        ],
        custom_models: true,
        upstream_providers: false,
      })),
    })
    render(<ExternalLabelingCard />)
  }

  it("groups unknown provider methods using the backend family name", async () => {
    const methods = [
      { id: "FUTURE_API", name: "Future API" },
      { id: "FUTURE_PLAN", name: "Future Plan" },
    ]
    appContext.current = {
      settings: settings("FUTURE_API", "future-model"),
      saveSettings: vi.fn(),
      externalIntegrations: methods.map(method => ({
        ...method,
        family: { id: "FUTURE_FAMILY", name: "Future Service" },
        type: ExternalIntegrationType.AI_PROVIDER,
        status: ExternalIntegrationStatus.ON,
        available: true,
      })),
      fetchExternalIntegrations: vi.fn(),
    }
    getExternalLabelingProviders.mockResolvedValue({
      providers: methods.map(method => ({
        id: method.id,
        connected: true,
        recommended_models: [
          { id: "future-model", name: "Future Model", probabilistic: false },
        ],
        custom_models: false,
        upstream_providers: false,
      })),
    })
    render(<ExternalLabelingCard />)
    fireEvent.click(await screen.findByTestId("external-add-provider"))
    const group = screen.getByRole("group", { name: "Future Service" })
    expect(within(group).getAllByRole("option")).toHaveLength(2)
    expect(
      within(group).getByTestId("external-provider-option-FUTURE_PLAN"),
    ).toHaveTextContent("Future Plan")
    expect(
      within(group).getByTestId("external-provider-option-FUTURE_PLAN"),
    ).not.toHaveTextContent("Future Service")
    fireEvent.click(
      within(group).getByTestId("external-provider-option-FUTURE_PLAN"),
    )
    expect(screen.getByTestId("external-priority-1")).toHaveTextContent(
      "Future Service - Future Plan",
    )
  })

  it("preserves unavailable entries during reorder and uses the next ready priority", async () => {
    renderPriorities(["CLAUDE_AGENT", "OPENROUTER"])
    const first = await screen.findByTestId("external-priority-0")
    expect(first).toHaveTextContent(external.priorityStates.unavailableHere)
    expect(screen.getByTestId("external-priority-1")).toHaveTextContent(
      external.preferredHere,
    )
    expect(screen.getByTestId("external-entry-editor")).toBeDisabled()
    expect(
      screen.queryByTestId("external-priority-notice"),
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId("external-priority-info"))
    const info = screen.getByRole("dialog", { name: external.priorityTitle })
    expect(
      within(info).getByTestId("external-priority-notice"),
    ).toHaveTextContent(external.platformPriorityNotice)
    fireEvent.keyDown(info, { key: "Escape" })
    expect(
      screen.queryByTestId("external-priority-notice"),
    ).not.toBeInTheDocument()
    fireEvent.click(
      within(first).getByRole("button", { name: external.moveDown }),
    )
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: {
          external: expect.objectContaining({
            providers: [
              {
                provider: "OPENROUTER",
                model: "router-model",
                upstreamProvider: null,
              },
              {
                provider: "CLAUDE_AGENT",
                model: "claude-model",
                upstreamProvider: null,
              },
            ],
          }),
        },
      }),
    )
  })

  it("leaves priorities unchanged when the add picker is dismissed", async () => {
    renderPriorities()
    const add = await screen.findByTestId("external-add-provider")
    fireEvent.click(add)
    const picker = screen.getByRole("listbox")
    expect(
      within(picker).getByTestId("external-provider-option-OPENAI"),
    ).toHaveTextContent("OPENAI")
    expect(screen.queryByTestId("external-priority-1")).not.toBeInTheDocument()
    fireEvent.keyDown(picker, { key: "Escape" })
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
    expect(screen.queryByTestId("external-priority-1")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: en.common.save }),
    ).not.toBeInTheDocument()
  })

  it.each([
    ["CHATGPT", "chat-model"],
    ["OPENROUTER", "router-model"],
  ])("preserves model edits when adding %s", async (providerId, modelId) => {
    renderPriorities()
    await screen.findByTestId("external-priority-0")
    fireEvent.click(
      screen.getByRole("radio", { name: new RegExp(external.customModel) }),
    )
    fireEvent.change(
      screen.getByRole("textbox", { name: external.customModel }),
      { target: { value: "edited-model" } },
    )
    fireEvent.click(screen.getByTestId("external-add-provider"))
    fireEvent.click(
      screen.getByTestId(`external-provider-option-${providerId}`),
    )
    expect(screen.getByTestId("external-priority-0")).toHaveTextContent(
      "edited-model",
    )
    expect(screen.getByTestId("external-priority-1")).toHaveTextContent(modelId)
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: {
          external: expect.objectContaining({
            providers: [
              {
                provider: "OPENROUTER",
                model: "edited-model",
                upstreamProvider: null,
              },
              { provider: providerId, model: modelId, upstreamProvider: null },
            ],
          }),
        },
      }),
    )
  })

  it("allows adding providers while editing an unavailable priority", async () => {
    renderPriorities(["CLAUDE_AGENT"])
    await screen.findByTestId("external-priority-0")
    expect(screen.getByTestId("external-entry-editor")).toBeDisabled()
    fireEvent.click(screen.getByTestId("external-add-provider"))
    fireEvent.click(screen.getByTestId("external-provider-option-OPENAI"))
    expect(screen.getByTestId("external-priority-0")).toHaveTextContent(
      "claude-model",
    )
    expect(screen.getByTestId("external-priority-1")).toHaveTextContent(
      "api-model",
    )
    expect(screen.getByTestId("external-entry-editor")).not.toBeDisabled()
  })

  it("adds at most five entries and supports keyboard ordering", async () => {
    renderPriorities()
    const add = await screen.findByTestId("external-add-provider")
    fireEvent.click(add)
    expect(screen.queryByTestId("external-priority-1")).not.toBeInTheDocument()
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId("external-provider-option-CHATGPT"))
    await waitFor(() =>
      expect(screen.getByTestId("external-priority-1")).toHaveTextContent(
        "chat-model",
      ),
    )
    fireEvent.click(add)
    fireEvent.click(screen.getByTestId("external-provider-option-OPENAI"))
    await waitFor(() =>
      expect(screen.getByTestId("external-priority-2")).toHaveTextContent(
        "api-model",
      ),
    )
    fireEvent.keyDown(
      within(screen.getByTestId("external-priority-2")).getByRole("button", {
        name: external.reorderProvider.replace("{provider}", "OPENAI"),
      }),
      { key: "ArrowUp" },
    )
    expect(screen.getByTestId("external-priority-1")).toHaveTextContent(
      "api-model",
    )
    expect(add).not.toBeDisabled()
    fireEvent.click(add)
    fireEvent.click(screen.getByTestId("external-provider-option-OPENAI"))
    fireEvent.click(add)
    fireEvent.click(screen.getByTestId("external-provider-option-CHATGPT"))
    await waitFor(() =>
      expect(screen.getByTestId("external-priority-4")).toBeInTheDocument(),
    )
    expect(add).toBeDisabled()
  })

  it("keeps edits when changing the active priority", async () => {
    renderPriorities(["OPENROUTER", "CHATGPT"])
    await screen.findByTestId("external-priority-0")
    fireEvent.click(
      screen.getByRole("radio", { name: new RegExp(external.customModel) }),
    )
    fireEvent.change(
      screen.getByRole("textbox", { name: external.customModel }),
      { target: { value: "edited-model" } },
    )
    fireEvent.click(
      screen.getByRole("button", {
        name: external.editProvider.replace("{provider}", "CHATGPT"),
      }),
    )
    expect(screen.getByTestId("external-priority-0")).toHaveTextContent(
      "edited-model",
    )
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: {
          external: expect.objectContaining({
            providers: [
              {
                provider: "OPENROUTER",
                model: "edited-model",
                upstreamProvider: null,
              },
              {
                provider: "CHATGPT",
                model: "chat-model",
                upstreamProvider: null,
              },
            ],
          }),
        },
      }),
    )
  })

  it("preserves edits and priorities when disabling suggestions", async () => {
    renderPriorities(["OPENROUTER", "CHATGPT"])
    await screen.findByTestId("external-priority-0")
    fireEvent.click(
      screen.getByRole("radio", { name: new RegExp(external.customModel) }),
    )
    fireEvent.change(
      screen.getByRole("textbox", { name: external.customModel }),
      { target: { value: "edited-model" } },
    )
    fireEvent.click(screen.getByTestId("external-labeling-switch"))
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: {
          external: expect.objectContaining({
            enabled: false,
            providers: [
              {
                provider: "OPENROUTER",
                model: "edited-model",
                upstreamProvider: null,
              },
              {
                provider: "CHATGPT",
                model: "chat-model",
                upstreamProvider: null,
              },
            ],
          }),
        },
      }),
    )
  })

  it("keeps duplicate selections editable without row key collisions", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {})
    renderPriorities(["OPENROUTER", "CHATGPT"])
    await screen.findByTestId("external-priority-1")
    fireEvent.click(screen.getByTestId("external-add-provider"))
    fireEvent.click(screen.getByTestId("external-provider-option-OPENROUTER"))
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        external.duplicateProvider,
      ),
    )
    expect(screen.getByRole("button", { name: en.common.save })).toBeDisabled()
    expect(consoleError).not.toHaveBeenCalled()
    fireEvent.click(
      within(screen.getByTestId("external-priority-2")).getByRole("button", {
        name: external.removeProvider.replace("{provider}", "OPENROUTER"),
      }),
    )
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("allows removing the final entry without recreating it", async () => {
    renderPriorities()
    await screen.findByTestId("external-priority-0")
    fireEvent.click(
      screen.getByRole("button", {
        name: external.removeProvider.replace("{provider}", "OPENROUTER"),
      }),
    )
    expect(screen.queryByTestId("external-priority-0")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: { external: expect.objectContaining({ providers: [] }) },
      }),
    )
  })

  it("opens provider setup on the integrations providers tab", async () => {
    getExternalLabelingModels.mockResolvedValue({ models: [] })
    renderCard({ ...COMPATIBLE_PROVIDER, connected: false })

    fireEvent.click(
      await screen.findByRole("button", { name: external.connectProvider }),
    )

    expect(navigate).toHaveBeenCalledWith(
      "/entities?tab=providers&focus=OPENAI_COMPATIBLE",
    )
  })

  it("only lists installed models for local models", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: [
        { id: "org/model-GGUF:Q4_K_M", name: "Model", probabilistic: false },
      ],
    })
    renderCard(LOCAL_PROVIDER, "org/model-GGUF:Q4_K_M")

    const options = await screen.findByTestId("external-model-options")
    await waitFor(() =>
      expect(within(options).getByRole("radio")).toBeChecked(),
    )
    expect(screen.getAllByRole("radio")).toHaveLength(1)
    expect(screen.queryByText(external.customModel)).not.toBeInTheDocument()
    expect(
      screen.queryByText(external.customModelNotice),
    ).not.toBeInTheDocument()
  })

  it("warns when the selected model failed to start", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: [
        {
          id: "org/bad-GGUF:Q8_0",
          name: "Bad",
          probabilistic: false,
          load_failed: true,
        },
        { id: "org/good-GGUF:Q4_K_M", name: "Good", probabilistic: false },
      ],
    })
    renderCard(LOCAL_PROVIDER, "org/bad-GGUF:Q8_0")

    expect(
      await screen.findByTestId("external-model-load-failed"),
    ).toHaveTextContent(external.modelLoadFailed.replace("{model}", "Bad"))
    expect(screen.getAllByText(external.modelFailed)).toHaveLength(1)

    fireEvent.click(screen.getByRole("radio", { name: /Good/ }))
    expect(
      screen.queryByTestId("external-model-load-failed"),
    ).not.toBeInTheDocument()
  })

  it("warns about small models", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: [
        {
          id: "org/small-GGUF:Q4_K_M",
          name: "Small",
          probabilistic: false,
          size: 806_000_000,
        },
        {
          id: "org/large-GGUF:Q4_K_M",
          name: "Large",
          probabilistic: false,
          size: 2_500_000_000,
        },
      ],
    })
    renderCard(LOCAL_PROVIDER, "org/small-GGUF:Q4_K_M")

    expect(
      await screen.findByTestId("external-small-model-warning"),
    ).toHaveTextContent(external.smallModelWarning)

    fireEvent.click(screen.getByRole("radio", { name: /Large/ }))
    expect(
      screen.queryByTestId("external-small-model-warning"),
    ).not.toBeInTheDocument()
  })

  it("offers other models for providers that accept them", async () => {
    getExternalLabelingModels.mockResolvedValue({ models: [] })
    renderCard(COMPATIBLE_PROVIDER)

    expect(await screen.findByText(external.customModel)).toBeInTheDocument()
    expect(
      screen.queryByTestId("external-manage-models"),
    ).not.toBeInTheDocument()
  })

  it("keeps unlisted models of custom endpoints without validating them", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: [{ id: "listed", name: "listed", probabilistic: false }],
    })
    renderCard(COMPATIBLE_PROVIDER, "proxy/unlisted")

    expect(
      await screen.findByLabelText(external.customModel, {
        selector: "input:not([type=radio])",
      }),
    ).toHaveValue("proxy/unlisted")
    expect(
      screen.getByText(external.customModelUnlistedHint),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: external.validate }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        external.modelUnavailable.replace("{model}", "proxy/unlisted"),
      ),
    ).not.toBeInTheDocument()
  })

  it("shows token prices and keeps a delisted Copilot model selected", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: [
        {
          id: "gpt-6-luna",
          name: "GPT-6 Luna",
          probabilistic: false,
          pricing: {
            input_per_million: 0.1,
            output_per_million: 0.5,
            currency: "USD",
          },
        },
        {
          id: "claude-haiku",
          name: "Claude Haiku",
          probabilistic: false,
          pricing: {
            input_per_million: 0.125,
            output_per_million: 14,
            currency: "USD",
          },
        },
        { id: "auto", name: "Auto", probabilistic: false },
      ],
    })
    renderCard(COPILOT_PROVIDER, "retired-model")

    const options = await screen.findByTestId("external-model-options")
    expect(within(options).getByText("$0.10 / $0.50 per 1M")).toHaveAttribute(
      "title",
      external.tokenPriceHint,
    )
    expect(
      within(options).getByText("$0.125 / $14.00 per 1M"),
    ).toBeInTheDocument()
    expect(within(options).getAllByText(/per 1M/)).toHaveLength(2)
    expect(
      screen.getByText(
        external.modelUnavailable.replace("{model}", "retired-model"),
      ),
    ).toBeInTheDocument()
    expect(within(options).getAllByRole("radio")).toHaveLength(3)
    expect(screen.queryByText(external.customModel)).not.toBeInTheDocument()
  })

  it("filters long model lists", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta"].map(
        name => ({ id: `org/${name}`, name, probabilistic: false }),
      ),
    })
    renderCard(COMPATIBLE_PROVIDER, "org/alpha")

    const search = await screen.findByLabelText(external.searchModels)
    const options = screen.getByTestId("external-model-options")
    expect(within(options).getAllByRole("radio")).toHaveLength(7)

    fireEvent.change(search, { target: { value: "ZET" } })
    expect(within(options).getAllByRole("radio")).toHaveLength(1)
    expect(
      within(options).getByRole("radio", { name: /zeta/ }),
    ).toBeInTheDocument()

    fireEvent.change(search, { target: { value: "nothing" } })
    expect(screen.getByText(external.noModelsMatch)).toBeInTheDocument()
  })

  it("keeps a provider that is not available on this device", async () => {
    appContext.current = {
      settings: settings("LOCAL_MODELS", "org/model-GGUF:Q4_K_M"),
      saveSettings: vi.fn(),
      externalIntegrations: [
        { id: "LOCAL_MODELS", name: "Local models", available: false },
      ],
      fetchExternalIntegrations: vi.fn(),
      showToast: vi.fn(),
    }
    getExternalLabelingProviders.mockResolvedValue({
      providers: [COMPATIBLE_PROVIDER],
    })
    getExternalLabelingModels.mockResolvedValue({ models: [] })
    render(<ExternalLabelingCard />)

    expect(
      await screen.findByTestId("external-provider-unavailable"),
    ).toHaveTextContent(
      external.providerUnavailable.replace("{provider}", "Local models"),
    )
    expect(screen.getByTestId("external-entry-editor")).toHaveTextContent(
      "Local models",
    )
    expect(screen.getByText(external.unavailableHere)).toBeInTheDocument()
    expect(screen.queryByRole("radio")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: en.common.save }),
    ).not.toBeInTheDocument()
    expect(getExternalLabelingModels).not.toHaveBeenCalled()
  })

  it("manages local models in place and refreshes the list", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const downloading = localModel({
      id: "org/new-GGUF:Q4_K_M",
      name: "New",
      state: LocalModelState.DOWNLOADING,
      size: 1000,
      downloaded: 500,
    })
    getExternalLabelingModels
      .mockResolvedValueOnce({ models: [] })
      .mockResolvedValue({
        models: [
          { id: "org/new-GGUF:Q4_K_M", name: "New", probabilistic: false },
        ],
      })
    getLocalModels
      .mockResolvedValueOnce(overview([downloading]))
      .mockResolvedValue(
        overview([{ ...downloading, state: LocalModelState.UNLOADED }]),
      )
    renderCard(LOCAL_PROVIDER)

    expect(
      await screen.findByText(external.noModelsAvailable),
    ).toBeInTheDocument()
    expect(getLocalModels).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId("external-manage-models"))
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText(localCopy.dialogTitle)).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
    expect(
      await within(dialog).findByText(`${localCopy.states.DOWNLOADING} 50%`),
    ).toBeInTheDocument()
    expect(getExternalLabelingModels).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    await waitFor(() =>
      expect(getExternalLabelingModels).toHaveBeenCalledTimes(2),
    )
    const options = await screen.findByTestId("external-model-options")
    expect(within(options).getByRole("radio")).toBeChecked()

    fireEvent.click(
      within(dialog).getByRole("button", { name: en.common.close }),
    )
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    )
    expect(getExternalLabelingModels).toHaveBeenCalledTimes(3)
  })

  it("asks the catalog for labeling eligibility and shows input badges", async () => {
    getExternalLabelingModels.mockResolvedValue({
      models: [
        {
          id: "vision",
          name: "Vision",
          probabilistic: false,
          eligible: true,
          input_modalities: [
            AIInputModality.TEXT,
            AIInputModality.IMAGE,
            AIInputModality.DOCUMENT,
          ],
        },
        { id: "embed", name: "Embed", probabilistic: false, eligible: false },
      ],
    })
    renderCard(COMPATIBLE_PROVIDER, "vision")

    const options = await screen.findByTestId("external-model-options")
    expect(getExternalLabelingProviders).toHaveBeenCalledWith("LABELING")
    expect(getExternalLabelingModels).toHaveBeenCalledWith(
      "OPENAI_COMPATIBLE",
      "LABELING",
    )
    expect(
      within(options).getByText(en.settings.aiModalities.IMAGE),
    ).toBeTruthy()
    expect(
      within(options).getByText(en.settings.aiModalities.DOCUMENT),
    ).toBeTruthy()
    expect(
      within(options).getByText(en.settings.aiModalities.notEligible),
    ).toBeTruthy()
    expect(within(options).getByRole("radio", { name: /Embed/ })).toBeDisabled()
  })
})

describe("ExternalLabelingCard default AI models", () => {
  const shared = [
    { provider: "OPENROUTER", model: "router-model", upstreamProvider: null },
  ]
  const renderShared = () => {
    const configured = settings("OPENROUTER")
    configured.labeling.external.providers = []
    appContext.current = {
      settings: { ...configured, ai: { providers: shared } },
      saveSettings: vi.fn(),
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
    getExternalLabelingProviders.mockResolvedValue({
      providers: [
        {
          id: "OPENROUTER",
          connected: true,
          recommended_models: [
            { id: "router-model", name: "router-model", probabilistic: false },
          ],
          custom_models: true,
          upstream_providers: false,
        },
      ],
    })
    render(<ExternalLabelingCard />)
  }

  it("shows the default list read-only until labeling gets its own", async () => {
    renderShared()

    const row = await screen.findByTestId("external-priority-0")
    expect(row).toHaveTextContent("router-model")
    expect(row).toHaveTextContent(external.preferredHere)
    expect(screen.getByTestId("external-editor")).toHaveAttribute(
      "aria-disabled",
      "true",
    )
    expect(
      screen.queryByTestId("external-add-provider"),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("external-custom-toggle")).not.toBeChecked()

    fireEvent.click(screen.getByTestId("external-edit-default"))
    expect(navigate).toHaveBeenCalledWith("/settings?tab=ai&focus=AI_MODELS")
  })

  it("customizing starts from the default list and can be reverted", async () => {
    renderShared()

    fireEvent.click(await screen.findByTestId("external-custom-toggle"))
    expect(screen.getByTestId("external-custom-loading")).toBeInTheDocument()
    expect(
      screen.queryByTestId("external-custom-toggle"),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("external-editor")).toHaveAttribute(
      "aria-disabled",
      "true",
    )
    expect(screen.getByTestId("external-priority-0")).toHaveTextContent(
      "router-model",
    )
    await waitFor(() =>
      expect(screen.getByTestId("external-editor")).not.toHaveAttribute(
        "aria-disabled",
      ),
    )
    expect(
      screen.queryByTestId("external-custom-loading"),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("external-custom-toggle")).toBeChecked()
    expect(screen.getByTestId("external-priority-0")).toHaveTextContent(
      "router-model",
    )
    fireEvent.click(screen.getByTestId("external-add-provider"))
    expect(
      screen.getByTestId("external-provider-option-OPENROUTER"),
    ).toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" })
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        labeling: { external: expect.objectContaining({ providers: shared }) },
      }),
    )

    fireEvent.click(screen.getByTestId("external-custom-toggle"))
    expect(
      await screen.findByTestId("external-edit-default"),
    ).toBeInTheDocument()
    expect(screen.getByTestId("external-editor")).toHaveAttribute(
      "aria-disabled",
      "true",
    )
    expect(
      screen.queryByRole("button", { name: en.common.save }),
    ).not.toBeInTheDocument()
  })

  it("customizing drops default models that can't label", async () => {
    const decisions = {
      provider: "OPENROUTER",
      model: "embed-model",
      upstreamProvider: null,
    }
    shared.push(decisions)
    validateAIModel.mockResolvedValue({
      valid: false,
      name: "Embed",
      capabilities: [],
    })
    try {
      renderShared()

      fireEvent.click(await screen.findByTestId("external-custom-toggle"))

      await waitFor(() =>
        expect(screen.getByTestId("external-editor")).not.toHaveAttribute(
          "aria-disabled",
        ),
      )
      expect(screen.queryByTestId("external-priority-1")).toBeNull()
      expect(screen.getByTestId("external-priority-0")).toHaveTextContent(
        "router-model",
      )
      expect(validateAIModel).toHaveBeenCalledWith(
        "OPENROUTER",
        "embed-model",
        "LABELING",
        null,
      )
      expect(validateAIModel).toHaveBeenCalledTimes(1)
    } finally {
      shared.pop()
    }
  })
})
