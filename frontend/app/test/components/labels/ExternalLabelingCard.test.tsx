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
  LocalModelSource,
  LocalModelState,
  LocalRuntimeMode,
  LocalRuntimeSource,
  type LocalModel,
  type LocalModelsOverview,
} from "@/types/ai"
import { LabelOrigin } from "@/types/transactions"
import type {
  ExternalLabelingProviderDetails,
  ExternalLabelingSettings,
} from "@/types/labeling"
import en from "@/i18n/locales/en.json"

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
  appContext: { current: {} as Record<string, unknown> },
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => appContext.current,
}))
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }))
vi.mock("@/services/api", () => ({
  getExternalLabelingProviders,
  getExternalLabelingModels,
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

const LOCAL_PROVIDER: ExternalLabelingProviderDetails = {
  id: "LOCAL_MODELS",
  connected: true,
  recommended_models: [],
  custom_models: false,
  upstream_providers: false,
  dynamic_models: true,
}

const COMPATIBLE_PROVIDER: ExternalLabelingProviderDetails = {
  id: "OPENAI_COMPATIBLE",
  connected: true,
  recommended_models: [],
  custom_models: true,
  upstream_providers: false,
  dynamic_models: true,
}

const settings = (provider: string, model: string | null = null) => {
  const externalSettings: ExternalLabelingSettings = {
    enabled: true,
    provider,
    model,
    upstreamProvider: null,
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
  provider: ExternalLabelingProviderDetails,
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
  getApiServerInfo.mockResolvedValue({ isCustomServer: false })
})

afterEach(() => {
  vi.useRealTimers()
})

describe("ExternalLabelingCard models", () => {
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
    expect(screen.getByRole("combobox")).toHaveTextContent("Local models")
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
})
