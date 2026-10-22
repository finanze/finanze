import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { AdvancedSettingsForm } from "@/components/ui/AdvancedSettingsForm"
import en from "@/i18n/locales/en.json"

const { checkStatus, getConfig, hasConfig } = vi.hoisted(() => ({
  checkStatus: vi.fn(),
  getConfig: vi.fn(),
  hasConfig: vi.fn(),
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({ t: en, locale: "en-US" }),
}))
vi.mock("@/services/api", () => ({ checkStatus }))
vi.mock("@/services/configStorage", () => ({
  getConfig,
  saveConfig: vi.fn(),
  resetConfig: vi.fn(),
  hasConfig,
}))
vi.mock("@/components/ui/ConfirmationDialog", () => ({
  ConfirmationDialog: () => null,
}))

const copy = en.advancedSettings
const dataDirectory = "/home/user/.local/share/Finanze"
const logDirectory = `${dataDirectory}/logs`

const setIpc = (ipc: Partial<NonNullable<Window["ipcAPI"]>> | undefined) => {
  Object.defineProperty(window, "ipcAPI", {
    value: ipc,
    configurable: true,
    writable: true,
  })
}

const renderForm = () => render(<AdvancedSettingsForm />)

beforeEach(() => {
  vi.clearAllMocks()
  getConfig.mockReturnValue({})
  hasConfig.mockReturnValue(false)
  checkStatus.mockResolvedValue({
    server: {
      options: { dataDir: dataDirectory, logDir: logDirectory },
    },
  })
  setIpc(undefined)
})

afterEach(() => {
  cleanup()
  setIpc(undefined)
})

describe("AdvancedSettingsForm", () => {
  it("opens the local data and log directories from their adjacent buttons", async () => {
    const showItemInFolder = vi.fn().mockResolvedValue(undefined)
    setIpc({ showItemInFolder })
    renderForm()

    fireEvent.click(
      await screen.findByRole("button", {
        name: `${copy.openFolder}: ${copy.dataDir}`,
      }),
    )
    fireEvent.click(
      screen.getByRole("button", {
        name: `${copy.openFolder}: ${copy.logDir}`,
      }),
    )

    expect(showItemInFolder).toHaveBeenNthCalledWith(1, dataDirectory)
    expect(showItemInFolder).toHaveBeenNthCalledWith(2, logDirectory)
  })

  it("hides directory open buttons when using a remote backend", async () => {
    getConfig.mockReturnValue({ serverUrl: "https://finanze.example" })
    setIpc({ showItemInFolder: vi.fn() })
    renderForm()

    expect(await screen.findByText(copy.remoteServerNotice)).toBeInTheDocument()
    expect(
      screen.queryByRole("button", {
        name: `${copy.openFolder}: ${copy.dataDir}`,
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", {
        name: `${copy.openFolder}: ${copy.logDir}`,
      }),
    ).not.toBeInTheDocument()
  })

  it("hides directory open buttons when the desktop bridge is unavailable", async () => {
    renderForm()

    await screen.findByText(dataDirectory)
    expect(
      screen.queryByRole("button", {
        name: `${copy.openFolder}: ${copy.dataDir}`,
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", {
        name: `${copy.openFolder}: ${copy.logDir}`,
      }),
    ).not.toBeInTheDocument()
  })
})
