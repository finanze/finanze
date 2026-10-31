import { afterEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { AIServerDetailsDialog } from "@/components/settings/AIServerDetailsDialog"
import { AIServerError, AIServerKind, type AIServerInfo } from "@/types/ai"
import en from "@/i18n/locales/en.json"

const { getAIServerInfo } = vi.hoisted(() => ({ getAIServerInfo: vi.fn() }))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/services/api", () => ({ getAIServerInfo }))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))

const copy = en.settings.aiServer

const info = (overrides: Partial<AIServerInfo> = {}): AIServerInfo => ({
  url: "http://localhost:11434/v1",
  api_key_set: false,
  reachable: true,
  error: null,
  latency_ms: 12,
  kind: AIServerKind.OLLAMA,
  version: "0.12.3",
  models: [
    {
      id: "qwen3:8b",
      decisions: false,
      loaded: true,
      size: 5 * 1024 ** 3,
      context_length: 8192,
    },
    { id: "laya", decisions: true, loaded: false },
  ],
  ...overrides,
})

const renderDialog = (provider: string | null = "OPENAI_COMPATIBLE") =>
  render(<AIServerDetailsDialog provider={provider} onClose={vi.fn()} />)

describe("AIServerDetailsDialog", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("shows the detected server, its models and their state", async () => {
    getAIServerInfo.mockResolvedValue(info())
    renderDialog()

    expect(await screen.findByTestId("ai-server-kind")).toHaveTextContent(
      "Ollama0.12.3",
    )
    expect(getAIServerInfo).toHaveBeenCalledWith("OPENAI_COMPATIBLE")
    expect(screen.getByTestId("ai-server-status")).toHaveTextContent(
      copy.connected,
    )
    expect(screen.getByText("12 ms")).toBeInTheDocument()
    expect(screen.getByText("http://localhost:11434/v1")).toBeInTheDocument()
    expect(screen.getByText(copy.apiKeyNotSet)).toBeInTheDocument()
    expect(screen.getByText("2 available · 1 loaded")).toBeInTheDocument()

    const loaded = within(screen.getByTestId("ai-server-model-qwen3:8b"))
    expect(loaded.getByText(copy.loaded)).toBeInTheDocument()
    expect(loaded.getByText("8K context")).toBeInTheDocument()
    expect(loaded.getByText("5 GB")).toBeInTheDocument()

    const decision = within(screen.getByTestId("ai-server-model-laya"))
    expect(decision.getByText(copy.notLoaded)).toBeInTheDocument()
    expect(decision.getByText(copy.decisions)).toBeInTheDocument()
    expect(screen.queryByText(copy.unknownHint)).not.toBeInTheDocument()
  })

  it("explains unknown servers without loaded state", async () => {
    getAIServerInfo.mockResolvedValue(
      info({
        kind: null,
        version: null,
        api_key_set: true,
        models: [{ id: "gpt-x", decisions: false }],
      }),
    )
    renderDialog()

    expect(await screen.findByTestId("ai-server-kind")).toHaveTextContent(
      copy.unknownServer,
    )
    expect(screen.getByText(copy.apiKeySet)).toBeInTheDocument()
    expect(screen.getByText("1 available")).toBeInTheDocument()
    expect(screen.getByText(copy.unknownHint)).toBeInTheDocument()
    expect(screen.queryByText(copy.loaded)).not.toBeInTheDocument()
  })

  it.each([
    [false, AIServerError.UNREACHABLE, copy.unreachable],
    [true, AIServerError.UNAUTHORIZED, copy.respondedWithError],
  ])(
    "shows the error explanation (reachable=%s, %s)",
    async (reachable, error, status) => {
      getAIServerInfo.mockResolvedValue(
        info({ reachable, error, latency_ms: null, kind: null, models: [] }),
      )
      renderDialog()

      expect(await screen.findByTestId("ai-server-error")).toHaveTextContent(
        copy.errors[error],
      )
      expect(screen.getByTestId("ai-server-status")).toHaveTextContent(status)
      expect(screen.queryByText(copy.noModels)).not.toBeInTheDocument()
    },
  )

  it("refreshes on demand", async () => {
    getAIServerInfo.mockResolvedValueOnce(
      info({ reachable: false, error: AIServerError.UNREACHABLE, models: [] }),
    )
    getAIServerInfo.mockResolvedValueOnce(info())
    renderDialog()

    await screen.findByTestId("ai-server-error")
    fireEvent.click(screen.getByRole("button", { name: copy.refresh }))

    await waitFor(() =>
      expect(screen.getByTestId("ai-server-status")).toHaveTextContent(
        copy.connected,
      ),
    )
    expect(getAIServerInfo).toHaveBeenCalledTimes(2)
  })

  it("does not load while closed", () => {
    renderDialog(null)
    expect(getAIServerInfo).not.toHaveBeenCalled()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("shows a fetch error when the request fails", async () => {
    getAIServerInfo.mockRejectedValue(new Error("boom"))
    renderDialog()

    expect(await screen.findByText(en.common.fetchError)).toBeInTheDocument()
  })
})
