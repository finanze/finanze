import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { LabelingRuleDialog } from "@/components/labels/LabelingRuleDialog"
import {
  LabelCategory,
  LabelingRuleKind,
  TextMatchField,
  TextMatchOperator,
  type Label,
  type LabelingRule,
} from "@/types/labeling"
import { TxType } from "@/types/transactions"
import type { LabelableTx } from "@/components/labels/TransactionLabelsDialog"
import en from "@/i18n/locales/en.json"

const {
  createLabelingRule,
  updateLabelingRule,
  previewLabelingRule,
  showToast,
} = vi.hoisted(() => ({
  createLabelingRule: vi.fn(),
  updateLabelingRule: vi.fn(),
  previewLabelingRule: vi.fn(),
  showToast: vi.fn(),
}))

const labels: Label[] = [
  { id: "groceries", name: "Groceries", category: LabelCategory.EXPENSE },
  {
    id: "transfer",
    key: "internal_transfer",
    name: "Internal transfer",
    category: LabelCategory.EXCLUDED,
  },
]

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    entities: [],
    showToast,
    settings: { general: { defaultCurrency: "EUR" } },
  }),
}))
vi.mock("@/context/FinancialDataContext", () => ({
  useFinancialData: () => ({ positionsData: null }),
}))
vi.mock("@/context/LabelsContext", () => ({
  useLabels: () => ({
    labels,
    getLabelName: (label: Label) => label.name || label.key,
  }),
}))
vi.mock("@/services/api", () => ({
  createLabelingRule,
  updateLabelingRule,
  previewLabelingRule,
  getImageUrl: vi.fn(),
}))
vi.mock("@/hooks/useModalBackHandler", () => ({ useModalBackHandler: vi.fn() }))

const rules = en.labels.rules

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  createLabelingRule.mockResolvedValue({ applied: 0 })
  updateLabelingRule.mockResolvedValue({ applied: 0 })
})

const renderDialog = (
  props: { rule?: LabelingRule | null; fromTx?: LabelableTx | null } = {},
) => {
  const onSaved = vi.fn()
  render(
    <LabelingRuleDialog
      isOpen
      rule={props.rule ?? null}
      fromTx={props.fromTx}
      onClose={vi.fn()}
      onSaved={onSaved}
    />,
  )
  return { onSaved }
}

const groups = () => screen.getAllByTestId("rule-condition-group")

const textInput = (index: number) =>
  within(groups()[index]).getByTestId("rule-text-value")

const typeText = (index: number, value: string) =>
  fireEvent.change(textInput(index), { target: { value } })

const addAlternative = () =>
  fireEvent.click(screen.getByTestId("rule-add-alternative"))

const selectLabel = (name: string) =>
  fireEvent.click(screen.getByRole("button", { name }))

const save = () => fireEvent.click(screen.getByRole("button", { name: "Save" }))

const savedRequest = () => createLabelingRule.mock.calls[0][0]

describe("LabelingRuleDialog alternatives", () => {
  it("saves every alternative with its text values", async () => {
    const { onSaved } = renderDialog()
    expect(groups()).toHaveLength(1)
    expect(screen.queryByTestId("rule-or-divider")).not.toBeInTheDocument()

    typeText(0, "Mercadona, Lidl")
    addAlternative()
    expect(groups()).toHaveLength(2)
    expect(screen.getByTestId("rule-or-divider")).toHaveTextContent(rules.or)
    expect(screen.getByText(rules.alternativesHint)).toBeInTheDocument()
    await waitFor(() => expect(textInput(1)).toHaveFocus())

    typeText(1, "aldi")
    fireEvent.click(
      within(groups()[1]).getByRole("button", {
        name: en.enums.transactionType.FEE,
      }),
    )
    selectLabel("Groceries")
    save()

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    const request = savedRequest()
    expect(request.kind).toBe(LabelingRuleKind.MATCH)
    expect(request.labels).toEqual(["groceries"])
    expect(request.conditions).toHaveLength(2)
    expect(request.conditions[0].text).toEqual({
      values: ["Mercadona", "Lidl"],
      field: TextMatchField.ANY,
      operator: TextMatchOperator.CONTAINS,
    })
    expect(request.conditions[0].types).toBeNull()
    expect(request.conditions[1].text.values).toEqual(["aldi"])
    expect(request.conditions[1].types).toEqual([TxType.FEE])
  })

  it("keeps commas inside regex values", async () => {
    const { onSaved } = renderDialog()
    fireEvent.change(
      screen.getByRole("combobox", { name: rules.textOperator }),
      { target: { value: TextMatchOperator.REGEX } },
    )
    typeText(0, "^a{1,3}$")
    fireEvent.keyDown(textInput(0), { key: "Enter" })
    typeText(0, "b.*c")
    selectLabel("Groceries")
    save()

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(savedRequest().conditions[0].text).toEqual({
      values: ["^a{1,3}$", "b.*c"],
      field: TextMatchField.ANY,
      operator: TextMatchOperator.REGEX,
    })
  })

  it("asks for a condition in every alternative", () => {
    renderDialog()
    typeText(0, "netflix")
    addAlternative()
    selectLabel("Groceries")
    save()

    expect(screen.getByRole("alert")).toHaveTextContent(
      rules.alternativeConditionRequired.replace("{index}", "2"),
    )
    expect(createLabelingRule).not.toHaveBeenCalled()
  })

  it("removes alternatives back to a single group", async () => {
    const { onSaved } = renderDialog()
    typeText(0, "netflix")
    addAlternative()
    fireEvent.click(
      screen.getByRole("button", {
        name: rules.removeAlternative.replace("{index}", "2"),
      }),
    )
    await waitFor(() => expect(groups()).toHaveLength(1))
    expect(
      screen.queryByRole("button", {
        name: rules.removeAlternative.replace("{index}", "1"),
      }),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId("rule-or-divider")).not.toBeInTheDocument()
    selectLabel("Groceries")
    save()

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(savedRequest().conditions).toHaveLength(1)
  })

  it("limits the number of alternatives", () => {
    renderDialog()
    for (let i = 0; i < 4; i++) addAlternative()
    expect(groups()).toHaveLength(5)
    expect(screen.getByTestId("rule-add-alternative")).toBeDisabled()
    expect(
      screen.getByText(rules.maxAlternatives.replace("{max}", "5")),
    ).toBeInTheDocument()
  })

  it("edits a rule with several alternatives", async () => {
    renderDialog({
      rule: {
        id: "rule-1",
        name: "Supermarkets",
        enabled: true,
        kind: LabelingRuleKind.MATCH,
        label_ids: ["groceries"],
        conditions: [
          {
            text: {
              values: ["Mercadona", "Lidl"],
              field: TextMatchField.COUNTERPARTY,
              operator: TextMatchOperator.CONTAINS,
            },
          },
          { min_amount: 100, currency: "EUR" },
        ],
      },
    })

    expect(groups()).toHaveLength(2)
    expect(
      within(groups()[0])
        .getAllByTestId("tag-chip")
        .map(chip => chip.textContent),
    ).toEqual(["Mercadona", "Lidl"])
    expect(
      within(groups()[1]).getByRole("button", { name: rules.moreConditions }),
    ).toHaveAttribute("aria-expanded", "true")

    save()
    await waitFor(() => expect(updateLabelingRule).toHaveBeenCalled())
    const [id, request] = updateLabelingRule.mock.calls[0]
    expect(id).toBe("rule-1")
    expect(request.conditions).toHaveLength(2)
    expect(request.conditions[0].text.values).toEqual(["Mercadona", "Lidl"])
    expect(request.conditions[1].min_amount).toBe(100)
    expect(request.conditions[1].currency).toBe("EUR")
  })

  it("prefills the transaction text as a single value", async () => {
    const { onSaved } = renderDialog({
      fromTx: {
        id: "tx-1",
        name: "Card payment",
        counterparty: "Amazon, Inc.",
        amount: 10,
        currency: "EUR",
        type: TxType.FEE,
        date: "2024-01-01",
        labels: [{ label_id: "groceries" }],
      } as LabelableTx,
    })
    expect(
      within(groups()[0])
        .getAllByTestId("tag-chip")
        .map(chip => chip.textContent),
    ).toEqual(["Amazon, Inc."])
    save()

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(savedRequest().conditions).toEqual([
      expect.objectContaining({
        types: [TxType.FEE],
        text: {
          values: ["Amazon, Inc."],
          field: TextMatchField.COUNTERPARTY,
          operator: TextMatchOperator.CONTAINS,
        },
      }),
    ])
  })

  it("sends a single group for transfer rules", async () => {
    const { onSaved } = renderDialog()
    typeText(0, "netflix")
    addAlternative()
    fireEvent.click(screen.getByTestId("rule-kind-transfer"))
    expect(screen.queryByTestId("rule-add-alternative")).not.toBeInTheDocument()
    save()

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    const request = savedRequest()
    expect(request.kind).toBe(LabelingRuleKind.TRANSFER)
    expect(request.labels).toEqual(["transfer"])
    expect(request.conditions).toHaveLength(1)
    expect(request.conditions[0].max_days).toBe(3)
    expect(request.conditions[0]).not.toHaveProperty("text")
  })

  it("previews all alternatives", async () => {
    previewLabelingRule.mockResolvedValue({ count: 2, samples: [] })
    renderDialog()
    typeText(0, "netflix")
    addAlternative()
    typeText(1, "spotify")
    fireEvent.click(screen.getByRole("button", { name: rules.preview }))

    await waitFor(() =>
      expect(screen.getByTestId("rule-preview")).toHaveTextContent(
        rules.previewCount.replace("{count}", "2"),
      ),
    )
    const [conditions, limit] = previewLabelingRule.mock.calls[0]
    expect(limit).toBe(10)
    expect(
      conditions.map(
        (group: { text: { values: string[] } }) => group.text.values,
      ),
    ).toEqual([["netflix"], ["spotify"]])
  })
})
