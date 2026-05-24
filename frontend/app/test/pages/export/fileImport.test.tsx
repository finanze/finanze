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
  mockImportFile,
  mockGetTemplates,
} from "./setup"

function createTestFile(name = "data.csv", type = "text/csv") {
  return new File(["col1,col2\nval1,val2"], name, { type })
}

describe("file import dialog", () => {
  beforeEach(() => {
    cleanup()
    resetAllMocks()
  })

  async function openImportDialog() {
    mockGetTemplates.mockResolvedValue([])
    renderExportPage()

    await act(async () => {
      fireEvent.click(screen.getByRole("tab", { name: /Import/i }))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Import\.\.\./ }))
    })
  }

  it("opens the import dialog when clicking the import button", async () => {
    await openImportDialog()
    expect(screen.getByText("Import data from file")).toBeInTheDocument()
  })

  it("shows feature, file, and format selectors", async () => {
    await openImportDialog()
    expect(screen.getAllByText("Positions").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Transactions").length).toBeGreaterThan(0)
    expect(screen.getByText("File")).toBeInTheDocument()
  })

  it("shows validation errors when submitting without required fields", async () => {
    await openImportDialog()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })

    expect(
      screen.getByText("Select a feature to continue."),
    ).toBeInTheDocument()
    expect(screen.getByText("Choose a file to import.")).toBeInTheDocument()
    expect(mockImportFile).not.toHaveBeenCalled()
  })

  it("displays the selected file name after choosing a file", async () => {
    await openImportDialog()

    const fileInput = document.getElementById(
      "file-import-input",
    ) as HTMLInputElement
    const testFile = createTestFile("my-data.csv")

    fireEvent.change(fileInput, { target: { files: [testFile] } })

    await waitFor(() => {
      expect(screen.getByText("my-data.csv")).toBeInTheDocument()
    })
  })

  it("accepts a file via drag-and-drop", async () => {
    await openImportDialog()

    const dropZone = screen
      .getByText(/No file selected/)
      .closest("div[class*='border-dashed']")!

    const testFile = createTestFile("dropped-file.csv")

    fireEvent.drop(dropZone, {
      dataTransfer: { files: [testFile] },
    })

    await waitFor(() => {
      expect(screen.getByText("dropped-file.csv")).toBeInTheDocument()
    })
  })

  it("highlights the drop zone during drag over", async () => {
    await openImportDialog()

    const getDropZone = () =>
      screen
        .getByText(/No file selected/)
        .closest("div[class*='border-dashed']")!

    await act(async () => {
      fireEvent.dragEnter(getDropZone(), {
        dataTransfer: { files: [], types: ["Files"] },
      })
    })

    expect(getDropZone().className).toContain("border-primary")

    await act(async () => {
      fireEvent.dragLeave(getDropZone(), {
        dataTransfer: { files: [], types: ["Files"] },
      })
    })

    expect(getDropZone().className).not.toContain("border-primary")
  })

  it("closes dialog when cancel is clicked", async () => {
    await openImportDialog()
    expect(screen.getByText("Import data from file")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    })

    expect(screen.queryByText("Import data from file")).not.toBeInTheDocument()
  })
})
