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
import type { LabelingResult } from "@/types/labeling"

const { state, relabelTransactions } = vi.hoisted(() => ({
  state: { app: {} as Record<string, unknown> },
  relabelTransactions: vi.fn(),
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
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
  state.app = {
    entities: [],
    settings: {
      labeling: {
        external: {
          enabled: true,
          provider: "GITHUB_COPILOT",
          model: "retired-model",
          autoRun: true,
        },
      },
    },
    showToast: vi.fn(),
    externalIntegrations: [
      { id: "GITHUB_COPILOT", name: "GitHub Copilot", available: true },
    ],
    fetchExternalIntegrations: vi.fn(),
  }
})

afterEach(cleanup)

describe("RelabelDialog external failures", () => {
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
