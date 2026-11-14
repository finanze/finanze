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
  mockSuggestTemplateFields,
  buildImportResult,
  buildImportedTransactionData,
} from "./setup"
import { NumberFormat, TemplateType } from "@/types"
import { ProductType } from "@/types/position"

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

  it("shows feature, file, and format selectors with homogeneous required stars and no star on Template", async () => {
    await openImportDialog()
    const dialogHeading = screen.getByText("Import data from file")
    const motionWrapper = dialogHeading.closest("div.max-w-3xl")
    expect(motionWrapper).not.toBeNull()
    expect(motionWrapper?.className).toContain("w-full")
    expect(motionWrapper?.className).toContain("min-w-0")

    const featureLabel = screen.getByText("What to import?")
    expect(featureLabel.querySelector("span")?.className).toContain(
      "text-red-500",
    )
    const featureButtons = Array.from(
      featureLabel.parentElement!.querySelectorAll("button"),
    ).map(btn => btn.textContent?.trim())
    expect(featureButtons).toEqual(["Transactions", "Positions"])

    const fileLabel = screen.getByText("File")
    expect(fileLabel.querySelector("span")?.className).toContain("text-red-500")

    const templateLabel = screen.getByText("Template")
    expect(templateLabel.querySelector("span")).toBeNull()
    expect(templateLabel.textContent).toBe("Template")

    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })

    const productLabel = screen.getByText("Product")
    expect(productLabel.querySelector("span")?.className).toContain(
      "text-red-500",
    )
    expect(screen.getByText("Template").querySelector("span")).toBeNull()
  })

  it("opens the import dialog with the file filled when dropping or selecting on the import card", async () => {
    mockGetTemplates.mockResolvedValue([])
    renderExportPage()

    await act(async () => {
      fireEvent.click(screen.getByRole("tab", { name: /Import/i }))
    })

    expect(screen.queryByText(/Supported formats/)).not.toBeInTheDocument()

    const cardDropZone = screen
      .getByText("Drop a file here or click to browse")
      .closest("div[class*='border-dashed']")!

    const droppedFile = createTestFile("card-dropped.csv")
    await act(async () => {
      fireEvent.drop(cardDropZone, {
        dataTransfer: { files: [droppedFile] },
      })
    })

    expect(screen.getByText("Import data from file")).toBeInTheDocument()
    expect(screen.getByText("card-dropped.csv")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    })

    const cardInput = document.getElementById(
      "file-import-card-input",
    ) as HTMLInputElement
    const pickedFile = createTestFile("card-picked.csv")
    await act(async () => {
      fireEvent.change(cardInput, { target: { files: [pickedFile] } })
    })

    expect(screen.getByText("Import data from file")).toBeInTheDocument()
    expect(screen.getByText("card-picked.csv")).toBeInTheDocument()
  })

  it("shows validation errors when submitting without required fields", async () => {
    await openImportDialog()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })

    expect(
      screen.getByText("Select what to import to continue."),
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

  it("analyzes a file for template-less auto-import, allows format overrides, previews, and confirms import", async () => {
    mockSuggestTemplateFields.mockResolvedValue({
      headers: ["Fecha", "Concepto", "Importe", "Saldo"],
      fields: [
        { field: "date", name: "Fecha" },
        { field: "name", name: "Concepto" },
        { field: "amount", name: "Importe" },
      ],
      missing_required_fields: ["currency"],
      matching_templates: [],
      number_format: NumberFormat.EUROPEAN,
      date_format: "%d/%m/%Y",
      detected_currency: "USD",
    })
    mockImportFile
      .mockResolvedValueOnce(
        buildImportResult({ data: buildImportedTransactionData() }),
      )
      .mockResolvedValueOnce(
        buildImportResult({ data: buildImportedTransactionData() }),
      )

    await openImportDialog()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
    })

    const fileInput = document.getElementById(
      "file-import-input",
    ) as HTMLInputElement
    const statementFile = createTestFile("statement.csv")
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [statementFile] } })
    })

    await waitFor(() => {
      expect(screen.getByText("Ready to import")).toBeInTheDocument()
    })
    expect(
      screen.getByText("3 of 4 columns recognized automatically."),
    ).toBeInTheDocument()
    expect(screen.getByText("Detected from file")).toBeInTheDocument()
    expect(
      (document.getElementById("file-import-currency") as HTMLSelectElement)
        .value,
    ).toBe("USD")
    expect(
      screen.getByText(/Dates: DD\/MM\/YYYY · Decimals: 1\.000,00/),
    ).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })
    expect(
      screen.getByText("Select an entity to continue."),
    ).toBeInTheDocument()
    expect(mockImportFile).not.toHaveBeenCalled()

    await act(async () => {
      fireEvent.click(document.getElementById("file-import-entity")!)
    })
    expect(screen.getByText("Bank A")).toBeInTheDocument()
    expect(screen.queryByText("CryptoEx C")).not.toBeInTheDocument()
    await act(async () => {
      fireEvent.click(screen.getByText("Bank A"))
    })

    await act(async () => {
      fireEvent.click(screen.getByText("Format options"))
    })
    await act(async () => {
      fireEvent.change(document.getElementById("file-import-date-format")!, {
        target: { value: "%d-%m-%Y" },
      })
    })
    await act(async () => {
      fireEvent.change(
        document.getElementById("file-import-datetime-format")!,
        {
          target: { value: "%d-%m-%Y %H:%M:%S" },
        },
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })

    await waitFor(() => {
      expect(mockImportFile).toHaveBeenCalledTimes(1)
    })
    expect(mockImportFile).toHaveBeenCalledWith(
      expect.objectContaining({
        feature: "TRANSACTIONS",
        product: ProductType.ACCOUNT,
        number_format: NumberFormat.EUROPEAN,
        date_format: "%d-%m-%Y",
        datetime_format: "%d-%m-%Y %H:%M:%S",
        templateId: null,
        templateParams: { entity: "Bank A" },
        templateFields: [
          { field: "date", name: "Fecha" },
          { field: "name", name: "Concepto" },
          { field: "amount", name: "Importe" },
          { field: "currency", name: "currency", default: "USD" },
        ],
      }),
      statementFile,
    )

    expect(screen.getByText("Review simulated import")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Import data" }))
    })

    await waitFor(() => {
      expect(mockImportFile).toHaveBeenCalledTimes(2)
    })
    expect(mockImportFile).toHaveBeenLastCalledWith(
      expect.objectContaining({
        feature: "TRANSACTIONS",
        product: ProductType.ACCOUNT,
        preview: false,
        templateId: null,
        templateParams: { entity: "Bank A" },
      }),
      statementFile,
    )
  })

  it("auto-selects a matching template, allows crypto exchange entities for crypto, and surfaces file analysis errors", async () => {
    mockGetTemplates.mockResolvedValue([
      {
        id: "tpl-crypto",
        name: "Crypto Trades CSV",
        type: TemplateType.IMPORT,
        feature: "TRANSACTIONS",
        products: [ProductType.CRYPTO],
        fields: [{ field: "date", type: "DATETIME" }],
      },
    ])
    mockSuggestTemplateFields.mockResolvedValueOnce({
      headers: ["date", "symbol", "amount"],
      fields: [{ field: "date", name: "date" }],
      missing_required_fields: [],
      matching_templates: ["tpl-crypto"],
      number_format: NumberFormat.ENGLISH,
      date_format: "ISO",
      detected_currency: null,
    })

    renderExportPage()
    await act(async () => {
      fireEvent.click(screen.getByRole("tab", { name: /Import/i }))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Import\.\.\./ }))
    })
    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Crypto" }).at(-1)!)
    })

    const fileInput = document.getElementById(
      "file-import-input",
    ) as HTMLInputElement
    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [createTestFile("trades.csv")] },
      })
    })

    await waitFor(() => {
      expect(
        screen.getByText("Matches template “Crypto Trades CSV”."),
      ).toBeInTheDocument()
    })

    await act(async () => {
      fireEvent.click(document.getElementById("file-import-entity")!)
    })
    expect(screen.getByText("Bank A")).toBeInTheDocument()
    expect(screen.getByText("CryptoEx C")).toBeInTheDocument()

    const pdfErr = Object.assign(new Error("Scanned PDF"), {
      code: "PDF_NO_TEXT_LAYER",
    })
    mockSuggestTemplateFields.mockRejectedValueOnce(pdfErr)
    await act(async () => {
      fireEvent.change(document.getElementById("file-import-input")!, {
        target: { files: [createTestFile("scanned.pdf", "application/pdf")] },
      })
    })

    await waitFor(() => {
      expect(
        screen.getByText(/scanned images or vector outlines/i),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByText(
        "This file can't be read automatically. Try extracting it with AI.",
      ),
    ).toBeInTheDocument()
  })

  async function selectAccountTransactions() {
    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
    })
  }

  async function selectImage(name = "receipt.png") {
    const image = createTestFile(name, "image/png")
    await act(async () => {
      fireEvent.change(document.getElementById("file-import-input")!, {
        target: { files: [image] },
      })
    })
    return image
  }

  async function selectBankA() {
    await act(async () => {
      fireEvent.click(document.getElementById("file-import-entity")!)
    })
    await act(async () => {
      fireEvent.click(screen.getByText("Bank A"))
    })
  }

  it("extracts images with AI and confirms the stored preview by token", async () => {
    mockImportFile
      .mockResolvedValueOnce(
        buildImportResult({
          data: buildImportedTransactionData(),
          previewToken: "token-1",
          ai: {
            provider: "OPENAI",
            model: "gpt",
            rows: 1,
            requests: 1,
            images: true,
          },
        }),
      )
      .mockResolvedValueOnce(
        buildImportResult({ data: buildImportedTransactionData() }),
      )
    await openImportDialog()
    await selectAccountTransactions()
    const image = await selectImage()

    expect(
      (document.getElementById("file-import-use-ai") as HTMLButtonElement)
        .dataset.state,
    ).toBe("checked")
    expect(mockSuggestTemplateFields).not.toHaveBeenCalled()
    expect(screen.queryByText("Template")).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })
    expect(
      screen.getByText("Select an entity to continue."),
    ).toBeInTheDocument()
    expect(mockImportFile).not.toHaveBeenCalled()

    await selectBankA()
    expect(
      document.getElementById("file-import-ai-instructions"),
    ).not.toBeInTheDocument()
    await act(async () => {
      fireEvent.click(screen.getByTestId("file-import-ai-instructions-toggle"))
    })
    await act(async () => {
      fireEvent.change(
        document.getElementById("file-import-ai-instructions")!,
        { target: { value: "Ignore holds" } },
      )
    })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })

    await waitFor(() => {
      expect(mockImportFile).toHaveBeenCalledTimes(1)
    })
    expect(mockImportFile).toHaveBeenCalledWith(
      expect.objectContaining({
        useAi: true,
        aiInstructions: "Ignore holds",
        templateParams: { entity: "Bank A" },
      }),
      image,
    )
    expect(mockImportFile.mock.calls[0][0].templateFields).toBeUndefined()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Import data" }))
    })

    await waitFor(() => {
      expect(mockImportFile).toHaveBeenCalledTimes(2)
    })
    expect(mockImportFile).toHaveBeenLastCalledWith(
      expect.objectContaining({
        preview: false,
        previewToken: "token-1",
        useAi: true,
      }),
      null,
    )
  })

  it("continues an AI import in background and offers a review", async () => {
    let resolveImport: (value: unknown) => void = () => {}
    mockImportFile.mockReturnValueOnce(
      new Promise(resolve => {
        resolveImport = resolve
      }),
    )
    await openImportDialog()
    await selectAccountTransactions()
    await selectImage()
    await selectBankA()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("file-import-background"))
    })

    await waitFor(() => {
      expect(
        screen.queryByText("Import data from file"),
      ).not.toBeInTheDocument()
    })
    expect(screen.getByTestId("file-import-running")).toHaveTextContent(
      "Importing...",
    )
    expect(
      screen.queryByRole("button", { name: "Import..." }),
    ).not.toBeInTheDocument()

    await act(async () => {
      resolveImport(
        buildImportResult({
          data: buildImportedTransactionData(),
          previewToken: "token-2",
        }),
      )
    })

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Review" })).toBeInTheDocument()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Review" }))
    })
    expect(screen.getByText("Review simulated import")).toBeInTheDocument()
  })
})
