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
import { LocalModelsIntegration } from "@/components/settings/LocalModelsIntegration"
import { ramWarningRatio } from "@/components/settings/LocalModelsManager"
import {
  HuggingFaceModelKind,
  LocalModelSource,
  LocalModelState,
  LocalRuntimeMode,
  LocalRuntimeSource,
  type LocalModel,
  type LocalModelsOverview,
} from "@/types/ai"
import en from "@/i18n/locales/en.json"

const {
  getLocalModels,
  downloadLocalModel,
  deleteLocalModel,
  importLocalModel,
  getHuggingFaceQuants,
  getApiServerInfo,
  showToast,
} = vi.hoisted(() => ({
  getLocalModels: vi.fn(),
  downloadLocalModel: vi.fn(),
  deleteLocalModel: vi.fn(),
  importLocalModel: vi.fn(),
  getHuggingFaceQuants: vi.fn(),
  getApiServerInfo: vi.fn(),
  showToast: vi.fn(),
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({ showToast }),
}))
vi.mock("@/services/api", () => ({
  getLocalModels,
  downloadLocalModel,
  deleteLocalModel,
  importLocalModel,
  getHuggingFaceQuants,
  getApiServerInfo,
}))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))

const copy = en.settings.localModels

const CATALOG = [
  {
    id: "ggml-org/Laya-GGUF:Q8_0",
    name: "Laya",
    repo: "ggml-org/Laya-GGUF",
    quant: "Q8_0",
    size: 500_000_000,
    ram: 1_000_000_000,
    params: "0.4B",
    license: "apache-2.0",
    decisions: true,
  },
  {
    id: "unsloth/gemma-GGUF:Q4_K_M",
    name: "Gemma",
    repo: "unsloth/gemma-GGUF",
    quant: "Q4_K_M",
    size: 800_000_000,
    ram: 8_000_000_000,
    params: "1B",
    license: "gemma",
    decisions: false,
  },
]

const model = (overrides: Partial<LocalModel>): LocalModel => ({
  id: "org/model-GGUF:Q4_K_M",
  name: "org/model-GGUF:Q4_K_M",
  source: LocalModelSource.HUGGING_FACE,
  state: LocalModelState.UNLOADED,
  decisions: false,
  deletable: true,
  size: 1_000_000,
  ...overrides,
})

const overview = (
  overrides: Partial<LocalModelsOverview> = {},
): LocalModelsOverview => ({
  connected: false,
  capabilities: {
    built_in_available: true,
    can_import_files: true,
    env_api_key_set: false,
    system_memory: 8_000_000_000,
  },
  catalog: CATALOG,
  reachable: false,
  models: [],
  ...overrides,
})

const connected = (overrides: Partial<LocalModelsOverview> = {}) =>
  overview({
    connected: true,
    reachable: true,
    mode: LocalRuntimeMode.BUILT_IN,
    source: LocalRuntimeSource.BUILT_IN,
    models_folder: "/data/models/local",
    ...overrides,
  })

const renderIntegration = (enabled: boolean, openManager = false) => {
  const renderFields = vi.fn(() => <div data-testid="fields" />)
  const renderActions = vi.fn(() => <div data-testid="actions" />)
  const onServerModeChange = vi.fn()
  render(
    <LocalModelsIntegration
      enabled={enabled}
      openManager={openManager}
      renderFields={renderFields}
      renderActions={renderActions}
      onServerModeChange={onServerModeChange}
    />,
  )
  return { renderFields, renderActions, onServerModeChange }
}

const openDialog = async () => {
  fireEvent.click(await screen.findByRole("button", { name: copy.manage }))
  return screen.findByRole("dialog")
}

const setIpc = (ipc: Partial<NonNullable<Window["ipcAPI"]>> | undefined) => {
  Object.defineProperty(window, "ipcAPI", {
    value: ipc,
    configurable: true,
    writable: true,
  })
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  getApiServerInfo.mockResolvedValue({ isCustomServer: false })
  setIpc(undefined)
})

afterEach(() => {
  vi.useRealTimers()
})

describe("LocalModelsIntegration setup", () => {
  it("offers built-in and server modes", async () => {
    getLocalModels.mockResolvedValue(overview())
    const { renderFields, renderActions, onServerModeChange } =
      renderIntegration(false)

    const builtIn = await screen.findByRole("radio", { name: copy.builtInMode })
    expect(builtIn).toHaveAttribute("aria-checked", "true")
    expect(screen.getByText(copy.builtInNotice)).toBeInTheDocument()
    expect(screen.queryByTestId("fields")).not.toBeInTheDocument()
    expect(renderActions).toHaveBeenCalledWith({ setup: true })

    fireEvent.click(screen.getByRole("radio", { name: copy.serverMode }))
    expect(onServerModeChange).toHaveBeenCalledWith(true)
    expect(screen.getByText(copy.serverNotice)).toBeInTheDocument()
    expect(screen.getByTestId("fields")).toBeInTheDocument()
    expect(renderFields).toHaveBeenLastCalledWith({})
  })

  it("asks for a server when the built-in engine is unavailable", async () => {
    getLocalModels.mockResolvedValue(
      overview({
        capabilities: {
          built_in_available: false,
          can_import_files: false,
          env_api_key_set: false,
        },
      }),
    )
    renderIntegration(false)
    expect(await screen.findByTestId("fields")).toBeInTheDocument()
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument()
    expect(screen.getByText(copy.serverNotice)).toBeInTheDocument()
  })

  it("explains the environment server", async () => {
    getLocalModels.mockResolvedValue(
      overview({
        capabilities: {
          built_in_available: true,
          can_import_files: true,
          env_server_url: "http://llama:8080",
          env_api_key_set: true,
        },
      }),
    )
    const { renderFields } = renderIntegration(false)

    expect(await screen.findByTestId("fields")).toBeInTheDocument()
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument()
    expect(
      screen.getByText(
        copy.envUrlNotice
          .replace("{url}", "http://llama:8080")
          .replace("{key}", copy.envKeySuffix),
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(copy.precedence)).toBeInTheDocument()
    expect(renderFields).toHaveBeenLastCalledWith({
      placeholders: {
        server_url: "http://llama:8080",
        api_key: copy.envKeyPlaceholder,
      },
      labelSuffix: copy.overridesEnvironment,
    })
  })

  it("retries after a failed load", async () => {
    getLocalModels
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValueOnce(overview())
    renderIntegration(false)

    fireEvent.click(
      await screen.findByRole("button", { name: en.common.retry }),
    )
    expect(
      await screen.findByRole("radio", { name: copy.builtInMode }),
    ).toBeInTheDocument()
    expect(getLocalModels).toHaveBeenLastCalledWith(true)
  })
})

describe("LocalModelsIntegration connected", () => {
  it("shows status, installed models and remaining recommendations", async () => {
    getLocalModels.mockResolvedValue(
      connected({
        models: [
          model({
            id: CATALOG[0].id,
            name: "Laya",
            source: LocalModelSource.CATALOG,
            state: LocalModelState.LOADED,
            decisions: true,
          }),
        ],
      }),
    )
    const { renderActions } = renderIntegration(true)

    expect(await screen.findByText(copy.using.BUILT_IN)).toBeInTheDocument()
    expect(renderActions).toHaveBeenCalledWith({ setup: false })
    const card = screen.getByTestId("local-models-status")
    expect(within(card).getByText("Laya")).toBeInTheDocument()
    expect(screen.queryByTestId("local-models-manager")).not.toBeInTheDocument()

    const dialog = await openDialog()
    expect(within(dialog).getByText(copy.dialogTitle)).toBeInTheDocument()
    const installed = within(dialog).getByTestId(`local-model-${CATALOG[0].id}`)
    expect(within(installed).getByText(copy.states.LOADED)).toBeInTheDocument()
    expect(within(installed).getByText(copy.decisions)).toBeInTheDocument()
    expect(
      screen.queryByTestId(`local-catalog-${CATALOG[0].id}`),
    ).not.toBeInTheDocument()
    const gemma = screen.getByTestId(`local-catalog-${CATALOG[1].id}`)
    expect(within(gemma).getAllByText(copy.ramWarning).length).toBeGreaterThan(
      0,
    )

    fireEvent.click(
      within(dialog).getByRole("button", { name: en.common.close }),
    )
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    )
  })

  it("summarizes installed models in the card", async () => {
    getLocalModels.mockResolvedValue(
      connected({
        models: Array.from({ length: 7 }, (_, index) =>
          model({ id: `m${index}`, name: `model-${index}` }),
        ),
      }),
    )
    renderIntegration(true)

    expect(await screen.findByText("model-4")).toBeInTheDocument()
    expect(screen.queryByText("model-5")).not.toBeInTheDocument()
    expect(
      screen.getByText(copy.moreModels.replace("{count}", "2")),
    ).toBeInTheDocument()
  })

  it("prompts to manage models when there are none", async () => {
    getLocalModels.mockResolvedValue(connected())
    renderIntegration(true)

    expect(await screen.findByText(copy.noModels)).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: copy.manage }),
    ).toBeInTheDocument()
  })

  it("opens the manager when focused", async () => {
    getLocalModels.mockResolvedValue(connected())
    renderIntegration(true, true)

    const dialog = await screen.findByRole("dialog")
    expect(
      within(dialog).getByTestId("local-models-manager"),
    ).toBeInTheDocument()
  })

  it("shows unreachable servers with their error", async () => {
    getLocalModels.mockResolvedValue(
      connected({
        reachable: false,
        mode: LocalRuntimeMode.EXTERNAL,
        source: LocalRuntimeSource.PAYLOAD,
        server_url: "http://router:8080",
        error: "UNAUTHORIZED",
      }),
    )
    renderIntegration(true)

    expect(
      await screen.findByText(
        copy.using.PAYLOAD.replace("{url}", "http://router:8080"),
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(copy.unreachable)).toBeInTheDocument()
    expect(screen.getByText(copy.errors.UNAUTHORIZED)).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: copy.manage }),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId("local-models-manager")).not.toBeInTheDocument()
  })

  it("polls while a model is downloading", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const downloading = model({
      state: LocalModelState.DOWNLOADING,
      size: 1000,
      downloaded: 250,
    })
    getLocalModels
      .mockResolvedValueOnce(connected({ models: [downloading] }))
      .mockResolvedValue(
        connected({
          models: [{ ...downloading, state: LocalModelState.UNLOADED }],
        }),
      )
    renderIntegration(true)

    const card = await screen.findByTestId("local-models-status")
    expect(await within(card).findByText("25%")).toBeInTheDocument()
    const dialog = await openDialog()
    expect(
      within(dialog).getByText(`${copy.states.DOWNLOADING} 25%`),
    ).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(
      await within(dialog).findByText(copy.states.UNLOADED),
    ).toBeInTheDocument()
    expect(within(card).queryByText("25%")).not.toBeInTheDocument()
    const calls = getLocalModels.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(getLocalModels).toHaveBeenCalledTimes(calls)
  })
})

describe("LocalModelsManager", () => {
  it("hides import on web and shows it on desktop", async () => {
    getLocalModels.mockResolvedValue(connected())
    renderIntegration(true)
    await openDialog()
    await screen.findByTestId("local-models-manager")
    expect(
      screen.queryByRole("button", { name: copy.import }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: copy.openFolder }),
    ).not.toBeInTheDocument()

    cleanup()
    const selectFile = vi.fn().mockResolvedValue("/models/phi.gguf")
    const showItemInFolder = vi.fn()
    setIpc({ selectFile, showItemInFolder })
    importLocalModel.mockResolvedValue({
      id: "local/phi",
      path: "/models/phi.gguf",
    })
    renderIntegration(true)
    await openDialog()

    fireEvent.click(await screen.findByRole("button", { name: copy.import }))
    await waitFor(() =>
      expect(importLocalModel).toHaveBeenCalledWith("/models/phi.gguf"),
    )
    expect(selectFile).toHaveBeenCalledWith({
      title: copy.importTitle,
      extensions: ["gguf"],
    })
    expect(showToast).toHaveBeenCalledWith(
      copy.importSuccess.replace("{model}", "local/phi"),
      "success",
    )

    fireEvent.click(screen.getByRole("button", { name: copy.openFolder }))
    expect(showItemInFolder).toHaveBeenCalledWith("/data/models/local")
  })

  it("hides import for custom servers and external routers", async () => {
    setIpc({ selectFile: vi.fn(), showItemInFolder: vi.fn() })
    getApiServerInfo.mockResolvedValue({ isCustomServer: true })
    getLocalModels.mockResolvedValue(connected())
    renderIntegration(true)
    await openDialog()
    await screen.findByTestId("local-models-manager")
    await waitFor(() => expect(getApiServerInfo).toHaveBeenCalled())
    expect(
      screen.queryByRole("button", { name: copy.import }),
    ).not.toBeInTheDocument()

    cleanup()
    getApiServerInfo.mockResolvedValue({ isCustomServer: false })
    getLocalModels.mockResolvedValue(
      connected({
        mode: LocalRuntimeMode.EXTERNAL,
        source: LocalRuntimeSource.PAYLOAD,
        server_url: "http://router:8080",
        models_folder: null,
      }),
    )
    renderIntegration(true)
    await openDialog()
    expect(await screen.findByText(copy.externalHint)).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: copy.import }),
    ).not.toBeInTheDocument()
  })

  it("downloads recommended models", async () => {
    getLocalModels.mockResolvedValue(connected())
    downloadLocalModel.mockResolvedValue(undefined)
    renderIntegration(true)
    await openDialog()

    const laya = await screen.findByTestId(`local-catalog-${CATALOG[0].id}`)
    fireEvent.click(within(laya).getByRole("button"))
    await waitFor(() =>
      expect(downloadLocalModel).toHaveBeenCalledWith({
        catalog_id: CATALOG[0].id,
      }),
    )
    expect(showToast).toHaveBeenCalledWith(
      copy.downloadStarted.replace("{model}", "Laya"),
      "success",
    )
  })

  it("maps download errors", async () => {
    getLocalModels.mockResolvedValue(connected())
    downloadLocalModel.mockRejectedValue({ code: "INSUFFICIENT_SPACE" })
    renderIntegration(true)
    await openDialog()

    const laya = await screen.findByTestId(`local-catalog-${CATALOG[0].id}`)
    fireEvent.click(within(laya).getByRole("button"))
    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith(
        copy.errors.INSUFFICIENT_SPACE,
        "error",
        { reportable: false },
      ),
    )
  })

  it("finds and downloads Hugging Face quants", async () => {
    getLocalModels.mockResolvedValue(connected())
    getHuggingFaceQuants.mockResolvedValue({
      repo: "org/tiny-GGUF",
      quants: [
        { quant: "Q2_K", file: "tiny-Q2_K.gguf", size: 100 },
        { quant: "Q4_K_M", file: "tiny-Q4_K_M.gguf", size: 200 },
      ],
      kind: HuggingFaceModelKind.CHAT,
    })
    downloadLocalModel.mockResolvedValue(undefined)
    renderIntegration(true)
    await openDialog()

    const input = await screen.findByLabelText(copy.huggingFace)
    fireEvent.change(input, { target: { value: "not a repo" } })
    fireEvent.click(screen.getByRole("button", { name: copy.find }))
    expect(await screen.findByText(copy.invalidRepo)).toBeInTheDocument()
    expect(getHuggingFaceQuants).not.toHaveBeenCalled()

    fireEvent.change(input, {
      target: { value: "https://huggingface.co/org/tiny-GGUF/tree/main" },
    })
    fireEvent.click(screen.getByRole("button", { name: copy.find }))
    const variant = await screen.findByLabelText(copy.variant)
    expect(getHuggingFaceQuants).toHaveBeenCalledWith("org/tiny-GGUF")
    expect(variant).toHaveValue("Q4_K_M")

    fireEvent.click(
      within(variant.parentElement as HTMLElement).getByRole("button", {
        name: en.common.download,
      }),
    )
    await waitFor(() =>
      expect(downloadLocalModel).toHaveBeenCalledWith({
        repo: "org/tiny-GGUF",
        quant: "Q4_K_M",
      }),
    )
  })

  it("warns when a Hugging Face variant may not fit in memory", async () => {
    getLocalModels.mockResolvedValue(connected())
    getHuggingFaceQuants.mockResolvedValue({
      repo: "org/big-GGUF",
      quants: [
        { quant: "Q2_K", file: "big-Q2_K.gguf", size: 3_000_000_000 },
        { quant: "Q4_K_M", file: "big-Q4_K_M.gguf", size: 5_000_000_000 },
      ],
      kind: HuggingFaceModelKind.CHAT,
    })
    renderIntegration(true)
    await openDialog()

    const input = await screen.findByLabelText(copy.huggingFace)
    fireEvent.change(input, { target: { value: "org/big-GGUF" } })
    fireEvent.click(screen.getByRole("button", { name: copy.find }))
    const variant = await screen.findByLabelText(copy.variant)
    expect(screen.getByTestId("local-quant-ram-warning")).toHaveTextContent(
      copy.ramWarning,
    )

    fireEvent.change(variant, { target: { value: "Q2_K" } })
    expect(
      screen.queryByTestId("local-quant-ram-warning"),
    ).not.toBeInTheDocument()
  })

  it("blocks encoder models and warns about unverified ones", async () => {
    getLocalModels.mockResolvedValue(connected())
    getHuggingFaceQuants
      .mockResolvedValueOnce({
        repo: "org/encoder-GGUF",
        quants: [{ quant: "Q8_0", file: "enc-Q8_0.gguf", size: 100 }],
        kind: HuggingFaceModelKind.ENCODER,
      })
      .mockResolvedValueOnce({
        repo: "org/odd-GGUF",
        quants: [{ quant: "Q8_0", file: "odd-Q8_0.gguf", size: 100 }],
        kind: HuggingFaceModelKind.UNKNOWN,
      })
    renderIntegration(true)
    await openDialog()

    const input = await screen.findByLabelText(copy.huggingFace)
    fireEvent.change(input, { target: { value: "org/encoder-GGUF" } })
    fireEvent.click(screen.getByRole("button", { name: copy.find }))
    expect(
      await screen.findByTestId("local-model-unsupported"),
    ).toHaveTextContent(copy.errors.UNSUPPORTED_MODEL)
    expect(screen.queryByLabelText(copy.variant)).not.toBeInTheDocument()

    fireEvent.change(input, { target: { value: "org/odd-GGUF" } })
    fireEvent.click(screen.getByRole("button", { name: copy.find }))
    expect(await screen.findByLabelText(copy.variant)).toBeInTheDocument()
    expect(screen.getByText(copy.unverifiedModel)).toBeInTheDocument()
    expect(
      screen.queryByTestId("local-model-unsupported"),
    ).not.toBeInTheDocument()
    expect(downloadLocalModel).not.toHaveBeenCalled()
  })

  it("explains models that failed to start", async () => {
    getLocalModels.mockResolvedValue(
      connected({
        models: [
          model({
            id: "org/bad-GGUF:Q8_0",
            name: "bad",
            state: LocalModelState.FAILED,
          }),
        ],
      }),
    )
    renderIntegration(true)

    const card = await screen.findByTestId("local-models-status")
    expect(within(card).getByTitle(copy.states.FAILED)).toHaveTextContent("bad")
    const dialog = await openDialog()
    expect(
      within(dialog).getByTestId("local-model-failed-org/bad-GGUF:Q8_0"),
    ).toHaveTextContent(`${copy.failedHint} ${copy.failedLogHint}`)
  })

  it("confirms before deleting models", async () => {
    getLocalModels.mockResolvedValue(
      connected({
        models: [
          model({
            id: "local/phi",
            name: "phi",
            source: LocalModelSource.IMPORTED,
            path: "/models/phi.gguf",
          }),
          model({
            id: "server-model",
            name: "server-model",
            source: LocalModelSource.SERVER,
            deletable: false,
          }),
        ],
      }),
    )
    deleteLocalModel.mockResolvedValue(undefined)
    renderIntegration(true)
    await openDialog()

    const server = await screen.findByTestId("local-model-server-model")
    expect(
      within(server).queryByRole("button", { name: en.common.delete }),
    ).not.toBeInTheDocument()

    const phi = screen.getByTestId("local-model-local/phi")
    expect(within(phi).getByText("/models/phi.gguf")).toBeInTheDocument()
    fireEvent.click(within(phi).getByRole("button", { name: en.common.delete }))
    expect(
      screen.getByText(copy.deleteImportedMessage.replace("{model}", "phi")),
    ).toBeInTheDocument()
    expect(deleteLocalModel).not.toHaveBeenCalled()

    const dialogButtons = screen.getAllByRole("button", {
      name: en.common.delete,
    })
    fireEvent.click(dialogButtons[dialogButtons.length - 1])
    await waitFor(() =>
      expect(deleteLocalModel).toHaveBeenCalledWith("local/phi"),
    )
  })

  it("reports downloads that disappear", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    getLocalModels
      .mockResolvedValueOnce(
        connected({
          models: [model({ state: LocalModelState.DOWNLOADING })],
        }),
      )
      .mockResolvedValue(connected())
    renderIntegration(true)

    await screen.findByText("org/model-GGUF:Q4_K_M")
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    const failure = copy.downloadFailed.replace(
      "{model}",
      "org/model-GGUF:Q4_K_M",
    )
    expect(await screen.findByText(failure)).toBeInTheDocument()

    const dialog = await openDialog()
    expect(within(dialog).getByText(failure)).toBeInTheDocument()
    fireEvent.click(
      within(dialog).getAllByRole("button", { name: en.common.close })[1],
    )
    await waitFor(() =>
      expect(screen.queryByText(failure)).not.toBeInTheDocument(),
    )
  })

  it("does not report downloads listed under another tag", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    getLocalModels
      .mockResolvedValueOnce(
        connected({
          models: [model({ state: LocalModelState.DOWNLOADING })],
        }),
      )
      .mockResolvedValue(
        connected({
          models: [
            model({
              id: "org/model-GGUF:IMAT",
              name: "org/model-GGUF:IMAT",
              state: LocalModelState.UNLOADED,
            }),
          ],
        }),
      )
    renderIntegration(true)

    await screen.findByText("org/model-GGUF:Q4_K_M")
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(await screen.findByText("org/model-GGUF:IMAT")).toBeInTheDocument()
    expect(
      screen.queryByText(
        copy.downloadFailed.replace("{model}", "org/model-GGUF:Q4_K_M"),
      ),
    ).not.toBeInTheDocument()
  })
})

describe("ramWarningRatio", () => {
  const GIB = 1024 ** 3

  it.each([
    [2, 0.4],
    [4, 0.4],
    [6, 0.5],
    [8, 0.6],
    [12, 0.65],
    [16, 0.7],
    [24, 0.725],
    [32, 0.75],
    [64, 0.75],
  ])("uses the expected ratio for %i GiB", (gib, ratio) => {
    expect(ramWarningRatio(gib * GIB)).toBeCloseTo(ratio)
  })
})
