import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { AIModelsCard } from "@/components/ai/AIModelsCard"
import { ExternalIntegrationStatus, ExternalIntegrationType } from "@/types"
import en from "@/i18n/locales/en.json"

const { getAIProviders, getAIModels, validateAIModel, appContext, params } =
  vi.hoisted(() => ({
    getAIProviders: vi.fn(),
    getAIModels: vi.fn(),
    validateAIModel: vi.fn(),
    appContext: { current: {} as Record<string, unknown> },
    params: { current: new URLSearchParams() },
  }))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => appContext.current,
}))
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  useSearchParams: () => [params.current],
}))
vi.mock("@/services/api", () => ({
  getAIProviders,
  getAIModels,
  validateAIModel,
}))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))

const PROVIDERS = [
  {
    id: "OPENAI",
    connected: true,
    recommended_models: [
      { id: "gpt-6-luna", name: "GPT-6 Luna", probabilistic: true },
    ],
    custom_models: true,
    upstream_providers: false,
    attachments: true,
  },
]

const renderCard = (providers = [] as Record<string, unknown>[]) => {
  appContext.current = {
    settings: { ai: { providers } },
    saveSettings: vi.fn().mockResolvedValue(true),
    externalIntegrations: [
      {
        id: "OPENAI",
        name: "OpenAI",
        type: ExternalIntegrationType.AI_PROVIDER,
        status: ExternalIntegrationStatus.ON,
        available: true,
      },
    ],
    fetchExternalIntegrations: vi.fn(),
  }
  getAIProviders.mockResolvedValue({ providers: PROVIDERS })
  render(<AIModelsCard />)
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  params.current = new URLSearchParams()
})

describe("AIModelsCard", () => {
  it("edits and saves the default AI models for every feature", async () => {
    renderCard()

    expect(await screen.findByText(en.settings.aiModels.empty)).toBeTruthy()
    expect(getAIProviders).toHaveBeenCalledWith(undefined)
    fireEvent.click(await screen.findByTestId("ai-models-add-provider"))
    fireEvent.click(screen.getByTestId("ai-models-provider-option-OPENAI"))
    expect(screen.getByTestId("ai-models-priority-0")).toHaveTextContent(
      "gpt-6-luna",
    )
    fireEvent.click(screen.getByTestId("ai-models-save"))

    await waitFor(() =>
      expect(appContext.current.saveSettings).toHaveBeenCalledWith({
        ai: {
          providers: [
            { provider: "OPENAI", model: "gpt-6-luna", upstreamProvider: null },
          ],
        },
      }),
    )
  })

  it("is highlighted when focused from a feature", async () => {
    params.current = new URLSearchParams("tab=providers&focus=AI_MODELS")
    renderCard([
      { provider: "OPENAI", model: "gpt-6-luna", upstreamProvider: null },
    ])

    expect(await screen.findByTestId("ai-models-card")).toHaveClass("ring-2")
    expect(await screen.findByTestId("ai-models-priority-0")).toHaveTextContent(
      en.labels.external.preferredHere,
    )
    expect(screen.queryByTestId("ai-models-save")).not.toBeInTheDocument()
  })

  it("lists the models of a provider connected while the card is open", async () => {
    const compatible = {
      id: "OPENAI_COMPATIBLE",
      name: "Custom AI",
      type: ExternalIntegrationType.AI_PROVIDER,
      available: true,
    }
    const provider = (connected: boolean) => ({
      id: "OPENAI_COMPATIBLE",
      connected,
      recommended_models: [],
      custom_models: true,
      upstream_providers: false,
      dynamic_models: true,
    })
    appContext.current = {
      settings: { ai: { providers: [] } },
      saveSettings: vi.fn().mockResolvedValue(true),
      externalIntegrations: [
        { ...compatible, status: ExternalIntegrationStatus.OFF },
      ],
      fetchExternalIntegrations: vi.fn(),
    }
    getAIProviders.mockResolvedValueOnce({ providers: [provider(false)] })
    getAIModels.mockResolvedValue({
      models: [{ id: "server-model", name: "server-model" }],
    })
    const view = render(<AIModelsCard />)
    fireEvent.click(await screen.findByTestId("ai-models-add-provider"))
    fireEvent.click(
      screen.getByTestId("ai-models-provider-option-OPENAI_COMPATIBLE"),
    )
    expect(getAIModels).not.toHaveBeenCalled()

    getAIProviders.mockResolvedValueOnce({ providers: [provider(true)] })
    appContext.current = {
      ...appContext.current,
      externalIntegrations: [
        { ...compatible, status: ExternalIntegrationStatus.ON },
      ],
    }
    view.rerender(<AIModelsCard />)

    expect(await screen.findByText("server-model")).toBeInTheDocument()
    expect(getAIProviders).toHaveBeenCalledTimes(2)
    expect(getAIModels).toHaveBeenCalledWith("OPENAI_COMPATIBLE", undefined)
  })
})
