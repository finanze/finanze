import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { LabelDialog } from "@/components/labels/LabelDialog"
import { LabelGallery } from "@/components/labels/LabelGallery"
import { LabelCategory, LabelSubcategory, type Label } from "@/types/labeling"
import en from "@/i18n/locales/en.json"

const { createLabel, updateLabel, refreshLabels, showToast } = vi.hoisted(
  () => ({
    createLabel: vi.fn(),
    updateLabel: vi.fn(),
    refreshLabels: vi.fn(),
    showToast: vi.fn(),
  }),
)

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({ showToast }),
}))
vi.mock("@/context/LabelsContext", () => ({
  useLabels: () => ({
    refreshLabels,
    getLabelName: (label: Label) => label.name || label.key,
  }),
}))
vi.mock("@/services/api", () => ({ createLabel, updateLabel }))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))
vi.mock("@/components/ui/icon-picker", () => ({
  IconPicker: ({ children }: { children: ReactNode }) => <>{children}</>,
  Icon: () => <span />,
}))

const expense: Label = {
  id: "restaurants",
  name: "Restaurants",
  category: LabelCategory.EXPENSE,
  subcategory: LabelSubcategory.WANTS,
  protected: false,
}
const savings: Label = {
  id: "savings",
  name: "Savings",
  category: LabelCategory.EXCLUDED,
  subcategory: LabelSubcategory.SAVINGS,
  protected: false,
}
const transfer: Label = {
  id: "transfer",
  key: "internal_transfer",
  name: "Internal transfer",
  category: LabelCategory.EXCLUDED,
  subcategory: LabelSubcategory.NONE,
  protected: true,
  usage: 3,
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const renderDialog = (label: Label | null = null) => {
  const onClose = vi.fn()
  render(<LabelDialog isOpen label={label} onClose={onClose} />)
  return { onClose }
}

describe("LabelDialog subcategories", () => {
  it("keeps advanced options collapsed and offers only NEED/WANTS for expenses", () => {
    renderDialog()
    expect(
      screen.queryByRole("radiogroup", { name: en.labels.subcategory }),
    ).not.toBeInTheDocument()
    const advanced = screen.getByRole("button", { name: en.labels.advanced })
    expect(advanced).toHaveAttribute("aria-expanded", "false")
    fireEvent.click(advanced)
    const choices = within(
      screen.getByRole("radiogroup", { name: en.labels.subcategory }),
    )
    expect(choices.getAllByRole("radio")).toHaveLength(2)
    expect(
      choices.getByRole("radio", { name: en.labels.subcategories.NEED }),
    ).toHaveAttribute("aria-checked", "true")
    expect(
      choices.getByRole("radio", { name: en.labels.subcategories.WANTS }),
    ).toHaveAttribute("aria-checked", "false")
    fireEvent.click(advanced)
    expect(
      screen.queryByRole("radiogroup", { name: en.labels.subcategory }),
    ).not.toBeInTheDocument()
  })

  it("saves the chosen subcategory when creating an expense", async () => {
    const { onClose } = renderDialog()
    fireEvent.change(screen.getByLabelText(en.labels.labelName), {
      target: { value: "Leisure" },
    })
    fireEvent.click(screen.getByRole("button", { name: en.labels.advanced }))
    fireEvent.click(
      screen.getByRole("radio", { name: en.labels.subcategories.WANTS }),
    )
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(createLabel).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Leisure",
          category: LabelCategory.EXPENSE,
          subcategory: LabelSubcategory.WANTS,
        }),
      ),
    )
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
    expect(refreshLabels).toHaveBeenCalledOnce()
  })

  it("preserves an existing classification without opening advanced options", async () => {
    renderDialog(expense)
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(updateLabel).toHaveBeenCalledWith(
        expense.id,
        expect.objectContaining({ subcategory: LabelSubcategory.WANTS }),
      ),
    )
  })

  it("offers SAVINGS/NONE for excluded labels and resets to NONE for income", async () => {
    renderDialog(savings)
    fireEvent.click(screen.getByRole("button", { name: en.labels.advanced }))
    const choices = within(
      screen.getByRole("radiogroup", { name: en.labels.subcategory }),
    )
    expect(choices.getAllByRole("radio")).toHaveLength(2)
    expect(
      choices.getByRole("radio", { name: en.labels.subcategories.SAVINGS }),
    ).toHaveAttribute("aria-checked", "true")
    expect(
      choices.getByRole("radio", { name: en.labels.subcategories.NONE }),
    ).toHaveAttribute("aria-checked", "false")
    fireEvent.click(screen.getByTestId("label-category-income"))
    expect(
      screen.queryByRole("button", { name: en.labels.advanced }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("radiogroup", { name: en.labels.subcategory }),
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(updateLabel).toHaveBeenCalledWith(
        savings.id,
        expect.objectContaining({
          category: LabelCategory.INCOME,
          subcategory: LabelSubcategory.NONE,
        }),
      ),
    )
  })

  it("resets SAVINGS to NEED when changing to an expense", async () => {
    renderDialog(savings)
    fireEvent.click(screen.getByRole("button", { name: en.labels.advanced }))
    fireEvent.click(screen.getByTestId("label-category-expense"))
    expect(
      screen.getByRole("radio", { name: en.labels.subcategories.NEED }),
    ).toHaveAttribute("aria-checked", "true")
    expect(
      screen.queryByRole("radio", { name: en.labels.subcategories.SAVINGS }),
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.save }))
    await waitFor(() =>
      expect(updateLabel).toHaveBeenCalledWith(
        savings.id,
        expect.objectContaining({
          category: LabelCategory.EXPENSE,
          subcategory: LabelSubcategory.NEED,
        }),
      ),
    )
  })

  it("does not open an editor for a protected label", () => {
    renderDialog(transfer)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: en.common.save }),
    ).not.toBeInTheDocument()
    expect(updateLabel).not.toHaveBeenCalled()
  })
})

describe("LabelGallery protection", () => {
  it("removes edit/delete actions but keeps movement navigation for protected labels", () => {
    const onEdit = vi.fn()
    const onDelete = vi.fn()
    const onOpenMovements = vi.fn()
    render(
      <LabelGallery
        labels={[transfer]}
        getLabelName={label => label.name || ""}
        onEdit={onEdit}
        onDelete={onDelete}
        onOpenMovements={onOpenMovements}
      />,
    )
    const tile = screen.getByTestId("label-card-internal_transfer")
    expect(
      within(tile).queryByRole("button", { name: en.common.edit }),
    ).not.toBeInTheDocument()
    expect(
      within(tile).queryByRole("button", { name: en.common.delete }),
    ).not.toBeInTheDocument()
    expect(
      within(tile).getByLabelText(en.labels.protectedLabel),
    ).toBeInTheDocument()
    fireEvent.click(tile)
    fireEvent.keyDown(tile, { key: "Enter" })
    expect(onEdit).not.toHaveBeenCalled()
    expect(onDelete).not.toHaveBeenCalled()
    fireEvent.click(within(tile).getByRole("button", { name: "3 movements" }))
    expect(onOpenMovements).toHaveBeenCalledWith(transfer)
  })

  it("keeps edit/delete actions for ordinary labels", () => {
    const onEdit = vi.fn()
    const onDelete = vi.fn()
    render(
      <LabelGallery
        labels={[expense]}
        getLabelName={label => label.name || ""}
        onEdit={onEdit}
        onDelete={onDelete}
        onOpenMovements={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole("button", { name: en.common.edit }))
    expect(onEdit).toHaveBeenCalledWith(expense)
    fireEvent.click(screen.getByRole("button", { name: en.common.delete }))
    expect(onDelete).toHaveBeenCalledWith(expense)
  })
})
