import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { RelabelDialog } from "@/components/labels/RelabelDialog"
import en from "@/i18n/locales/en.json"
import es from "@/i18n/locales/es.json"
import itTranslations from "@/i18n/locales/it.json"
import type { LabelingResult, ExternalLabelingSettings } from "@/types/labeling"

const { state, relabelTransactions } = vi.hoisted(() => ({
  state: {
    app: {} as Record<string, unknown>,
    locale: "en-US" as "en-US" | "es-ES" | "it-IT",
  },
  relabelTransactions: vi.fn(),
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({
    t:
      state.locale === "es-ES"
        ? es
        : state.locale === "it-IT"
          ? itTranslations
          : en,
    locale: state.locale,
  }),
}))
vi.mock("@/context/AppContext", () => ({ useAppContext: () => state.app }))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))
vi.mock("@/components/labels/TransactionLabels", () => ({
  useLabelOptions: () => [],
}))
vi.mock("@/services/api", () => ({
  relabelTransactions,
  getImageUrl: vi.fn(),
}))

const relabel = en.labels.relabel

const labelingResult = (
  overrides: Partial<LabelingResult> = {},
): LabelingResult => ({
  processed: 1,
  linked: 0,
  paired: 0,
  rule_labeled: 0,
  external_labeled: 0,
  skipped_locked: 0,
  skipped_linked: 0,
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
  state.locale = "en-US"
  state.app = {
    entities: [],
    settings: {
      labeling: {
        external: {
          enabled: true,
          providers: [{ provider: "GITHUB_COPILOT", model: "retired-model" }],
          autoRun: true,
        },
      },
    },
    showToast: vi.fn(),
    externalIntegrations: [
      {
        id: "GITHUB_COPILOT",
        name: "GitHub Copilot",
        available: true,
        status: "ON",
      },
    ],
    fetchExternalIntegrations: vi.fn(),
  }
})

afterEach(cleanup)

describe("RelabelDialog external failures", () => {
  it.each([
    ["es-ES", es],
    ["it-IT", itTranslations],
  ] as const)(
    "localizes the actual fallback provider in %s without altering provenance",
    async (locale, translations) => {
      state.locale = locale
      const response = {
        matched: 1,
        result: labelingResult(),
        external: labelingResult({
          external_labeled: 1,
          external_provider: "OPENAI_COMPATIBLE",
          external_model: "locale-model",
        }),
      }
      relabelTransactions.mockResolvedValue(response)
      render(<RelabelDialog isOpen onClose={vi.fn()} />)
      fireEvent.click(
        screen.getByRole("button", { name: translations.labels.relabel.run }),
      )
      expect(
        await screen.findByTestId("relabel-provider-used"),
      ).toHaveTextContent(
        translations.labels.relabel.fallbackUsed
          .replace(
            "{provider}",
            translations.settings.integration.OPENAI_COMPATIBLE.name,
          )
          .replace("{model}", "locale-model"),
      )
      expect(response.external.external_provider).toBe("OPENAI_COMPATIBLE")
      expect(relabelTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ include_external: true, dry_run: false }),
      )
    },
  )

  it.each([
    { available: false, status: "ON" },
    { available: true, status: "OFF" },
    { available: true, status: "EXPIRED" },
  ])("uses the next priority when the first is ineligible", first => {
    const settings = state.app.settings as {
      labeling: { external: ExternalLabelingSettings }
    }
    settings.labeling.external.providers.push({
      provider: "OPENROUTER",
      model: "router-model",
    })
    state.app.externalIntegrations = [
      { id: "GITHUB_COPILOT", name: "GitHub Copilot", ...first },
      { id: "OPENROUTER", name: "OpenRouter", available: true, status: "ON" },
    ]
    render(<RelabelDialog isOpen onClose={vi.fn()} />)
    expect(
      screen.getByText(
        relabel.includeExternal.replace("{provider}", "OpenRouter"),
      ),
    ).toBeInTheDocument()
    expect(screen.getByText("router-model")).toBeInTheDocument()
  })

  it("hides external labeling when all configured methods are ineligible", () => {
    state.app.externalIntegrations = [
      {
        id: "GITHUB_COPILOT",
        name: "GitHub Copilot",
        available: false,
        status: "ON",
      },
    ]
    render(<RelabelDialog isOpen onClose={vi.fn()} />)
    expect(
      screen.queryByTestId("relabel-external-switch"),
    ).not.toBeInTheDocument()
  })

  it("reports the actual fallback provider and model", async () => {
    relabelTransactions.mockResolvedValue({
      matched: 1,
      result: labelingResult(),
      external: labelingResult({
        external_labeled: 1,
        external_provider: "OPENROUTER",
        external_model: "router-model",
      }),
    })
    state.app.externalIntegrations = [
      {
        id: "GITHUB_COPILOT",
        name: "GitHub Copilot",
        available: true,
        status: "ON",
      },
      { id: "OPENROUTER", name: "OpenRouter", available: true, status: "ON" },
    ]
    render(<RelabelDialog isOpen onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: relabel.run }))
    expect(
      await screen.findByTestId("relabel-provider-used"),
    ).toHaveTextContent(
      relabel.fallbackUsed
        .replace("{provider}", "OpenRouter")
        .replace("{model}", "router-model"),
    )
  })

  it.each([
    [
      {
        external_error: "ExternalLabelingUnavailable",
        external_error_details: "The selected model is no longer available",
        external_error_code: "MODEL_NOT_FOUND",
      },
      `${relabel.externalFailed}: ${relabel.externalModelUnavailable}`,
    ],
    [
      {
        external_error: "ExternalLabelingUnavailable",
        external_error_details: "GitHub Copilot usage limit reached",
        external_error_code: "INSUFFICIENT_FUNDS",
      },
      `${relabel.externalFailed}: GitHub Copilot usage limit reached`,
    ],
  ])("explains the external labeling error", async (external, message) => {
    relabelTransactions.mockResolvedValue({
      matched: 1,
      result: labelingResult(),
      external: labelingResult({ processed: 0, ...external }),
    })
    render(<RelabelDialog isOpen onClose={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: relabel.run }))

    await waitFor(() =>
      expect(state.app.showToast).toHaveBeenCalledWith(message, "warning"),
    )
    expect(relabelTransactions).toHaveBeenCalledWith(
      expect.objectContaining({ include_external: true, dry_run: false }),
    )
  })
})
