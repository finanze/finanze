import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { LabelsProvider, useLabels } from "@/context/LabelsContext"

const mocks = vi.hoisted(() => ({
  getLabels: vi.fn(),
  invalidateFlowsCache: vi.fn(),
}))

vi.mock("@/services/api", () => ({ getLabels: mocks.getLabels }))

vi.mock("@/context/FinancialDataContext", () => ({
  useFinancialData: () => ({
    invalidateFlowsCache: mocks.invalidateFlowsCache,
  }),
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({ t: { labels: { base: {} } }, locale: "en" }),
}))

function LabelsConsumer() {
  const { revision, refreshLabels } = useLabels()
  return (
    <>
      <output data-testid="labels-revision">{revision}</output>
      <button onClick={() => void refreshLabels()}>Refresh</button>
    </>
  )
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  mocks.getLabels.mockResolvedValue({ labels: [] })
})

describe("LabelsContext", () => {
  it("loads lazily and invalidates flow references only on subsequent refreshes", async () => {
    const { rerender } = render(
      <LabelsProvider>
        <span>Idle</span>
      </LabelsProvider>,
    )
    expect(mocks.getLabels).not.toHaveBeenCalled()

    rerender(
      <LabelsProvider>
        <LabelsConsumer />
      </LabelsProvider>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("labels-revision")).toHaveTextContent("1"),
    )
    expect(mocks.getLabels).toHaveBeenCalledTimes(1)
    expect(mocks.invalidateFlowsCache).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }))
    await waitFor(() =>
      expect(screen.getByTestId("labels-revision")).toHaveTextContent("2"),
    )
    expect(mocks.getLabels).toHaveBeenCalledTimes(2)
    expect(mocks.invalidateFlowsCache).toHaveBeenCalledTimes(1)
  })
})
