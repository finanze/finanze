import { describe, it, expect, beforeEach } from "vitest"
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  act,
} from "@testing-library/react"
import {
  renderExportPage,
  resetAllMocks,
  mockExportFile,
  mockGetTemplates,
  mockShowToast,
  mockSaveBlobToDevice,
  buildExportResult,
} from "./setup"

describe("file export dialog", () => {
  beforeEach(() => {
    cleanup()
    resetAllMocks()
  })

  async function openExportDialog() {
    mockGetTemplates.mockResolvedValue([])
    renderExportPage()
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Export\.\.\./ }))
    })
  }

  it("opens the export dialog when clicking the export button", async () => {
    await openExportDialog()
    expect(screen.getByText("Export data to file")).toBeInTheDocument()
  })

  it("shows feature selector in export dialog", async () => {
    await openExportDialog()
    expect(screen.getByText("Feature")).toBeInTheDocument()
    expect(screen.getAllByText("Positions").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Transactions").length).toBeGreaterThan(0)
  })

  it("shows format and decimal format selectors", async () => {
    await openExportDialog()
    expect(screen.getByText("Format")).toBeInTheDocument()
    expect(screen.getByText("CSV")).toBeInTheDocument()
    expect(screen.getByText("TSV")).toBeInTheDocument()
    expect(screen.getByText("Excel")).toBeInTheDocument()
    expect(screen.getByText("Decimal format")).toBeInTheDocument()
  })

  it("shows validation error when exporting without selecting a feature", async () => {
    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    expect(
      screen.getByText("Select a feature to continue."),
    ).toBeInTheDocument()
    expect(mockExportFile).not.toHaveBeenCalled()
  })

  it("calls exportFile and shows success toast on successful export", async () => {
    mockExportFile.mockResolvedValue(buildExportResult())
    mockSaveBlobToDevice.mockResolvedValue(true)

    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getByText("Auto Contributions"))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("Export started"),
        "success",
      )
    })
  })

  it("shows error toast when export fails", async () => {
    mockExportFile.mockRejectedValue(new Error("Network error"))

    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getByText("Auto Contributions"))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("couldn't export"),
        "error",
      )
    })
  })

  it("closes the dialog when cancel is clicked", async () => {
    await openExportDialog()
    expect(screen.getByText("Export data to file")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    })

    expect(screen.queryByText("Export data to file")).not.toBeInTheDocument()
  })

  it("shows product selector when a feature with products is selected", async () => {
    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions")[0])
    })

    expect(
      screen.getByText("Limit export to specific products"),
    ).toBeInTheDocument()
  })
})
