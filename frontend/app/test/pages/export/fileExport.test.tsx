import { describe, it, expect, beforeEach } from "vitest"
import { format, subMonths } from "date-fns"
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
  mockFinancialState,
  buildExportResult,
} from "./setup"
import { ProductType } from "@/types/position"

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

  it("shows features in order (Transactions, Positions, Auto Contributions, Historic Data) and expands secondary features via + in narrow view", async () => {
    await openExportDialog()
    const featureLabel = screen.getByText("What to export?")
    expect(featureLabel).toBeInTheDocument()
    const featureStar = featureLabel.querySelector("span")
    expect(featureStar).toHaveTextContent("*")
    expect(featureStar?.className).toContain("text-red-500")

    const featureSection = featureLabel.parentElement!
    const buttons = Array.from(featureSection.querySelectorAll("button"))
    expect(buttons.map(btn => btn.textContent?.trim())).toEqual([
      "Transactions",
      "Positions",
      "Auto Contributions",
      "Historic Data",
      "",
    ])

    const autoContribBtn = buttons[2]
    const historicBtn = buttons[3]
    expect(autoContribBtn.className).toContain("hidden sm:inline-flex")
    expect(historicBtn.className).toContain("hidden sm:inline-flex")

    const moreButton = screen.getByTestId("file-export-more-features")
    expect(moreButton.className).toContain("sm:hidden")

    await act(async () => {
      fireEvent.click(moreButton)
    })

    expect(
      screen.queryByTestId("file-export-more-features"),
    ).not.toBeInTheDocument()
    const expandedSection = screen.getByText("What to export?").parentElement!
    const expandedButtons = Array.from(
      expandedSection.querySelectorAll("button"),
    )
    expect(expandedButtons.map(btn => btn.textContent?.trim())).toEqual([
      "Transactions",
      "Positions",
      "Auto Contributions",
      "Historic Data",
    ])
    expect(expandedButtons[2].className).not.toContain("hidden sm:inline-flex")
    expect(expandedButtons[3].className).not.toContain("hidden sm:inline-flex")
  })

  it("opens the export dialog with preselected feature and products from held position quick export pills", async () => {
    mockGetTemplates.mockResolvedValue([])
    mockExportFile.mockResolvedValue(buildExportResult())
    mockSaveBlobToDevice.mockResolvedValue(true)
    mockFinancialState.positionsData = {
      positions: {
        "entity-1": [
          {
            id: "gp-1",
            products: {
              [ProductType.DEPOSIT]: { entries: [{ id: "dep-1" }] },
              [ProductType.FUND]: { entries: [{ id: "fund-1" }] },
              [ProductType.STOCK_ETF]: { entries: [{ id: "stk-1" }] },
            },
          },
        ],
      },
    }

    renderExportPage()

    expect(screen.queryByText(/Available formats/)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Deposit" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Fund & stock orders" }),
    ).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Fund & stock orders" }),
      )
    })

    expect(screen.getByText("Export data to file")).toBeInTheDocument()
    const today = new Date()
    const expectedSixMonthsFrom = format(subMonths(today, 6), "yyyy-MM-dd")
    const expectedToday = format(today, "yyyy-MM-dd")

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenCalledWith(
        expect.objectContaining({
          feature: "TRANSACTIONS",
          data: [ProductType.FUND, ProductType.STOCK_ETF],
          from_date: expectedSixMonthsFrom,
          to_date: expectedToday,
        }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Deposit" }))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenLastCalledWith(
        expect.objectContaining({
          feature: "POSITION",
          data: [ProductType.DEPOSIT],
          from_date: null,
          to_date: null,
        }),
      )
    })
  })

  it("shows fallback quick export presets when user holds no positions", async () => {
    mockGetTemplates.mockResolvedValue([])
    mockFinancialState.positionsData = null

    renderExportPage()

    expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Stock/ETF" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Account movements" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Fund & stock orders" }),
    ).toBeInTheDocument()
  })

  it("shows format, decimal format, date format, and datetime format preset badges with independent custom inputs", async () => {
    mockExportFile.mockResolvedValue(buildExportResult())
    mockSaveBlobToDevice.mockResolvedValue(true)

    await openExportDialog()
    expect(screen.getByText("Format")).toBeInTheDocument()
    const csvBadge = screen.getByRole("button", { name: "CSV" })
    const tsvBadge = screen.getByRole("button", { name: "TSV" })
    const excelBadge = screen.getByRole("button", { name: "Excel" })
    expect(csvBadge.className).toContain("rounded-full")
    expect(csvBadge).toHaveAttribute("aria-pressed", "true")
    expect(tsvBadge.className).toContain("rounded-full")
    expect(excelBadge.className).toContain("rounded-full")

    expect(screen.getByText("Decimal format")).toBeInTheDocument()
    const englishNumBadge = screen.getByRole("button", { name: "1,000.00" })
    expect(englishNumBadge.className).toContain("rounded-full")

    expect(screen.getByText("Date Format")).toBeInTheDocument()
    expect(screen.getByText("Datetime Format")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "ISO (YYYY-MM-DD)" }),
    ).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("button", { name: "ISO 8601" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(document.getElementById("file-export-date-format")).toBeNull()
    expect(document.getElementById("file-export-datetime-format")).toBeNull()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Auto Contributions").at(-1)!)
    })
    expect(screen.getByText("Date Format")).toBeInTheDocument()
    expect(screen.queryByText("Datetime Format")).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "DD/MM/YYYY" }))
    })
    expect(screen.getByRole("button", { name: "DD/MM/YYYY" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenCalledWith(
        expect.objectContaining({
          feature: "AUTO_CONTRIBUTIONS",
          date_format: "%d/%m/%Y",
          datetime_format: null,
        }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Export\.\.\./ }))
    })
    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    expect(screen.queryByText("Date Format")).not.toBeInTheDocument()
    expect(screen.getByText("Datetime Format")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
      fireEvent.click(
        screen.getByRole("button", { name: "DD/MM/YYYY HH:mm:ss" }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenLastCalledWith(
        expect.objectContaining({
          feature: "TRANSACTIONS",
          date_format: null,
          datetime_format: "%d/%m/%Y %H:%M:%S",
        }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Export\.\.\./ }))
    })
    await act(async () => {
      fireEvent.click(screen.getAllByText("Positions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
    })
    expect(screen.queryByText("Date Format")).not.toBeInTheDocument()
    expect(screen.queryByText("Datetime Format")).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Historic Data").at(-1)!)
    })
    expect(screen.getByText("Date Format")).toBeInTheDocument()
    expect(screen.getByText("Datetime Format")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Factoring" }).at(-1)!,
      )
      fireEvent.click(screen.getByTestId("file-export-date-format-custom"))
      fireEvent.click(screen.getByTestId("file-export-datetime-format-custom"))
    })

    expect(document.getElementById("file-export-date-format")).not.toBeNull()
    expect(
      document.getElementById("file-export-datetime-format"),
    ).not.toBeNull()

    await act(async () => {
      fireEvent.change(document.getElementById("file-export-date-format")!, {
        target: { value: "%Y.%m.%d" },
      })
    })
    await act(async () => {
      fireEvent.change(
        document.getElementById("file-export-datetime-format")!,
        {
          target: { value: "%Y.%m.%d %H:%M" },
        },
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenLastCalledWith(
        expect.objectContaining({
          feature: "HISTORIC",
          data: [ProductType.FACTORING],
          date_format: "%Y.%m.%d",
          datetime_format: "%Y.%m.%d %H:%M",
        }),
      )
    })
  })

  it("shows validation error when exporting without selecting a feature", async () => {
    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    expect(
      screen.getByText("Select what to export to continue."),
    ).toBeInTheDocument()
    expect(mockExportFile).not.toHaveBeenCalled()
  })

  it("calls exportFile and shows success toast on successful export", async () => {
    mockExportFile.mockResolvedValue(buildExportResult())
    mockSaveBlobToDevice.mockResolvedValue(true)

    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Auto Contributions").at(-1)!)
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
      fireEvent.click(screen.getAllByText("Auto Contributions").at(-1)!)
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
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })

    expect(screen.getByText("Select at least one product.")).toBeInTheDocument()
  })

  it("defaults transactions export to last 6 months and supports switching presets", async () => {
    mockExportFile.mockResolvedValue(buildExportResult())
    mockSaveBlobToDevice.mockResolvedValue(true)
    const today = new Date()
    const expectedSixMonthsFrom = format(subMonths(today, 6), "yyyy-MM-dd")
    const expectedToday = format(today, "yyyy-MM-dd")
    const lastYear = today.getFullYear() - 1

    await openExportDialog()
    expect(screen.queryByText("Date range")).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Positions").at(-1)!)
    })
    expect(screen.queryByText("Date range")).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    expect(screen.getByText("Date range")).toBeInTheDocument()
    expect(
      screen.queryByText(/leave empty to export all history/i),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Last 6 months" }),
    ).toHaveAttribute("aria-pressed", "true")

    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenCalledWith(
        expect.objectContaining({
          feature: "TRANSACTIONS",
          data: [ProductType.ACCOUNT],
          from_date: expectedSixMonthsFrom,
          to_date: expectedToday,
        }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Export\.\.\./ }))
    })
    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
      fireEvent.click(screen.getByRole("button", { name: "Last year" }))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenLastCalledWith(
        expect.objectContaining({
          feature: "TRANSACTIONS",
          data: [ProductType.ACCOUNT],
          from_date: `${lastYear}-01-01`,
          to_date: `${lastYear}-12-31`,
        }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Export\.\.\./ }))
    })
    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
      fireEvent.click(screen.getByRole("button", { name: "All time" }))
      fireEvent.click(screen.getByRole("button", { name: "Excel" }))
      fireEvent.click(screen.getByRole("button", { name: "1.000,00" }))
    })
    expect(screen.getByRole("button", { name: "All time" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenLastCalledWith(
        expect.objectContaining({
          feature: "TRANSACTIONS",
          format: "XLSX",
          number_format: "EUROPEAN",
          data: [ProductType.ACCOUNT],
          from_date: null,
          to_date: null,
        }),
      )
    })
  })

  it("hides temporal format selectors when the selected export template excludes temporal columns", async () => {
    mockExportFile.mockResolvedValue(buildExportResult())
    mockSaveBlobToDevice.mockResolvedValue(true)
    mockGetTemplates.mockResolvedValue([
      {
        id: "tpl-no-dates",
        name: "Amounts Only",
        type: "EXPORT",
        feature: "TRANSACTIONS",
        products: [ProductType.ACCOUNT],
        fields: [
          { field: "name", type: "TEXT" },
          { field: "amount", type: "DECIMAL" },
        ],
      },
    ])

    renderExportPage()
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Export\.\.\./ }))
    })
    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    expect(screen.getByText("Datetime Format")).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
      fireEvent.click(
        screen.getByRole("button", { name: "DD/MM/YYYY HH:mm:ss" }),
      )
    })

    await act(async () => {
      fireEvent.click(screen.getByText("Use all available columns"))
    })
    await act(async () => {
      fireEvent.click(screen.getByText("Amounts Only"))
    })

    expect(screen.queryByText("Datetime Format")).not.toBeInTheDocument()
    expect(screen.queryByText("Date Format")).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    await waitFor(() => {
      expect(mockExportFile).toHaveBeenCalledWith(
        expect.objectContaining({
          feature: "TRANSACTIONS",
          template: { id: "tpl-no-dates", params: null },
          date_format: null,
          datetime_format: null,
        }),
      )
    })
  })

  it("validates that start date is not after end date", async () => {
    await openExportDialog()

    await act(async () => {
      fireEvent.click(screen.getAllByText("Transactions").at(-1)!)
    })
    await act(async () => {
      fireEvent.click(
        screen.getAllByRole("button", { name: "Account" }).at(-1)!,
      )
      fireEvent.click(screen.getByRole("button", { name: "Last year" }))
    })

    const fromButton = document.getElementById("file-export-from-date")!
    const clearFrom = fromButton.parentElement?.querySelector(
      "button[aria-label]",
    ) as HTMLElement | null
    if (clearFrom) {
      await act(async () => {
        fireEvent.click(clearFrom)
      })
    } else {
      const xIcon = fromButton.parentElement?.querySelector("svg.lucide-x")
      if (xIcon?.parentElement) {
        await act(async () => {
          fireEvent.click(xIcon.parentElement!)
        })
      }
    }

    await act(async () => {
      fireEvent.click(document.getElementById("file-export-from-date")!)
    })
    const dayFifteen = screen
      .getAllByRole("button")
      .find(btn => btn.textContent?.trim() === "15")!
    await act(async () => {
      fireEvent.click(dayFifteen)
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Export" }))
    })

    expect(
      screen.getByText("The start date must not be after the end date."),
    ).toBeInTheDocument()
    expect(mockExportFile).not.toHaveBeenCalled()
  })
})
