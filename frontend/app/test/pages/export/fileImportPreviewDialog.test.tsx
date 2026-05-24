import { describe, it, expect, beforeEach } from "vitest"
import { cleanup, fireEvent, screen, act } from "@testing-library/react"
import {
  renderPreviewDialog,
  buildImportedPositionData,
  buildImportedTransactionData,
} from "./setup"
import { ImportErrorType, type ImportError } from "@/types"
import { ProductType } from "@/types/position"
import { FileImportPreviewDialog } from "@/components/FileImportPreviewDialog"

describe("FileImportPreviewDialog", () => {
  beforeEach(() => {
    cleanup()
  })

  it("does not render when isOpen is false", () => {
    renderPreviewDialog({ isOpen: false })
    expect(screen.queryByText("Import Preview")).not.toBeInTheDocument()
  })

  it("renders the dialog when isOpen is true", () => {
    renderPreviewDialog({ isOpen: true })
    expect(screen.getByText("Import Preview")).toBeInTheDocument()
    expect(
      screen.getByText("Review the data before importing"),
    ).toBeInTheDocument()
  })

  it("shows empty state when importData is null", () => {
    renderPreviewDialog({ isOpen: true, importData: null })
    expect(screen.getByText("No data to import")).toBeInTheDocument()
  })

  it("shows empty state when importData has no positions or transactions", () => {
    renderPreviewDialog({
      isOpen: true,
      importData: {
        positions: [],
        transactions: { account: [], investment: [] } as any,
      },
    })
    expect(screen.getByText("No data to import")).toBeInTheDocument()
  })

  it("displays position data with entity name and product type", () => {
    renderPreviewDialog({
      isOpen: true,
      importData: buildImportedPositionData(),
    })

    expect(screen.getByText("Positions")).toBeInTheDocument()
    expect(screen.getByText("Bank A")).toBeInTheDocument()
    expect(screen.getByText("Accounts")).toBeInTheDocument()
    expect(screen.getByText("2 entries total")).toBeInTheDocument()
  })

  it("displays transaction data with product type and count", () => {
    renderPreviewDialog({
      isOpen: true,
      importData: buildImportedTransactionData(),
    })

    expect(screen.getByText("Transactions")).toBeInTheDocument()
    expect(screen.getByText("Accounts")).toBeInTheDocument()
  })

  it("shows sample entries when product details are expanded", async () => {
    renderPreviewDialog({
      isOpen: true,
      importData: buildImportedPositionData(),
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Show details/ }))
    })

    expect(screen.getAllByText("Main Account").length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getAllByText("Savings Account").length,
    ).toBeGreaterThanOrEqual(1)
  })

  it("collapses product details when hide is clicked", async () => {
    renderPreviewDialog({
      isOpen: true,
      importData: buildImportedPositionData(),
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Show details/ }))
    })

    expect(screen.getAllByText("Main Account").length).toBeGreaterThanOrEqual(1)

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Hide details/ }))
    })

    expect(screen.queryByText("Sample entries:")).not.toBeInTheDocument()
  })

  it("limits sample entries to 3 and shows hidden count", () => {
    const manyEntries = {
      positions: [
        {
          entity: { id: "e1", name: "Bank" },
          products: {
            [ProductType.ACCOUNT]: {
              entries: Array.from({ length: 7 }, (_, i) => ({
                id: `acc-${i}`,
                name: `Account ${i}`,
                total: i * 100,
                currency: "EUR",
              })),
            },
          },
        },
      ] as any,
    }

    renderPreviewDialog({ isOpen: true, importData: manyEntries })

    expect(screen.getByText("7 entries total")).toBeInTheDocument()
  })

  it("displays warnings when infoWarnings are provided", () => {
    const warnings: ImportError[] = [
      {
        type: ImportErrorType.UNEXPECTED_COLUMN,
        entry: "Sheet1",
        detail: ["extra_col_1", "extra_col_2"],
      },
    ]

    renderPreviewDialog({
      isOpen: true,
      importData: buildImportedPositionData(),
      infoWarnings: warnings,
    })

    expect(screen.getByText("Warnings")).toBeInTheDocument()
    expect(screen.getByText("extra_col_1")).toBeInTheDocument()
    expect(screen.getByText("extra_col_2")).toBeInTheDocument()
  })

  it("calls onConfirm when confirm button is clicked", async () => {
    const { props } = renderPreviewDialog({
      isOpen: true,
      importData: buildImportedPositionData(),
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Confirm Import" }))
    })

    expect(props.onConfirm).toHaveBeenCalledTimes(1)
  })

  it("calls onClose when cancel button is clicked", async () => {
    const { props } = renderPreviewDialog({
      isOpen: true,
      importData: buildImportedPositionData(),
    })

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    })

    expect(props.onClose).toHaveBeenCalledTimes(1)
  })

  it("maintains hooks order when toggling isOpen rapidly (regression)", () => {
    const { rerender, props } = renderPreviewDialog({ isOpen: false })

    expect(() => {
      rerender(<FileImportPreviewDialog {...props} isOpen={true} />)
      rerender(<FileImportPreviewDialog {...props} isOpen={false} />)
      rerender(<FileImportPreviewDialog {...props} isOpen={true} />)
      rerender(<FileImportPreviewDialog {...props} isOpen={false} />)
    }).not.toThrow()
  })
})
