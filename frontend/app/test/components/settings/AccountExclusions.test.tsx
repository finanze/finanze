import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { useState } from "react"
import { MemoryRouter } from "react-router-dom"
import { AccountExclusionsEditor } from "@/components/settings/AccountExclusionsEditor"
import { GeneralTab } from "@/components/settings/GeneralTab"
import { I18nProvider } from "@/i18n"
import type { AccountExclusion } from "@/types/accountExclusions"
import en from "@/i18n/locales/en.json"

const mocks = vi.hoisted(() => ({
  save: vi.fn(),
  toast: vi.fn(),
}))
const crypto = { stablecoins: ["USDT"], hideUnknownTokens: true }
let rules: AccountExclusion[] = []
const contextSettings = {
  general: {
    defaultCurrency: "EUR",
    defaultCommodityWeightUnit: "GRAM",
    editMode: "QUICK",
  },
  assets: { crypto, accounts: { exclusions: rules } },
}

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    settings: contextSettings,
    saveSettings: mocks.save,
    showToast: mocks.toast,
    entities: [],
  }),
}))
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    logout: vi.fn(),
    startPasswordChange: vi.fn(),
  }),
}))
vi.mock("@/components/settings/PrivacyCard", () => ({
  PrivacyCard: () => null,
}))
vi.mock("@/hooks/useModalBackHandler", () => ({
  useModalBackHandler: () => {},
}))

const copy = en.settings.assets.accounts
const initialRule: AccountExclusion = { type: "IBAN", value: "ES1234567890" }

function Editor({ success = true }: { success?: boolean }) {
  const [entries, setEntries] = useState(rules)
  const [expanded, setExpanded] = useState(false)
  return (
    <AccountExclusionsEditor
      rules={entries}
      expanded={expanded}
      onToggle={() => setExpanded(previous => !previous)}
      onSave={async next => {
        mocks.save(next)
        if (success) setEntries(next)
        return success
      }}
    />
  )
}

function wrap(children: React.ReactNode) {
  contextSettings.assets.accounts.exclusions = rules
  return render(
    <MemoryRouter>
      <I18nProvider>{children}</I18nProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  rules = []
  contextSettings.general.editMode = "QUICK"
  mocks.save.mockResolvedValue(true)
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe("Account exclusions", () => {
  it("normalizes pasted IBANs, persists changes and explains follow-up fetching", async () => {
    wrap(<Editor />)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    expect(screen.getByText(copy.emptyState)).toBeVisible()
    expect(screen.getByText(copy.dataUnchanged)).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: copy.addIban }))
    fireEvent.change(screen.getByLabelText(copy.ibanLabel), {
      target: { value: " es12 3456 7890 " },
    })
    fireEvent.click(screen.getByRole("button", { name: copy.addIban }))
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith([initialRule]))
    expect(mocks.toast).toHaveBeenCalledWith(copy.rulesChanged, "success")
    expect(screen.getByText("ES12 3456 7890")).toBeVisible()
    expect(screen.queryByLabelText(copy.ibanLabel)).not.toBeInTheDocument()
  })

  it("rejects invalid and duplicate IBANs without saving and cancels with Escape", () => {
    rules = [initialRule]
    wrap(<Editor />)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    fireEvent.click(screen.getByRole("button", { name: copy.addIban }))
    const input = screen.getByLabelText(copy.ibanLabel)
    fireEvent.change(input, { target: { value: "ES-123" } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(screen.getByRole("alert")).toHaveTextContent(copy.invalidIban)
    fireEvent.change(input, { target: { value: " es1234567890 " } })
    fireEvent.click(screen.getByRole("button", { name: copy.addIban }))
    expect(screen.getByRole("alert")).toHaveTextContent(copy.duplicateIban)
    fireEvent.keyDown(input, { key: "Escape" })
    expect(screen.queryByLabelText(copy.ibanLabel)).not.toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(mocks.save).not.toHaveBeenCalled()
  })

  it("edits a rule and persists an explicit empty list when the last rule is removed", async () => {
    rules = [initialRule]
    wrap(<Editor />)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    fireEvent.click(screen.getByRole("button", { name: copy.editIban }))
    fireEvent.change(screen.getByLabelText(copy.ibanLabel), {
      target: { value: "ES999" },
    })
    fireEvent.click(screen.getByRole("button", { name: copy.saveIban }))
    await waitFor(() =>
      expect(mocks.save).toHaveBeenCalledWith([
        { type: "IBAN", value: "ES999" },
      ]),
    )
    fireEvent.click(screen.getByRole("button", { name: copy.removeIban }))
    await waitFor(() => expect(mocks.save).toHaveBeenLastCalledWith([]))
    expect(screen.getByText(copy.emptyState)).toBeVisible()
  })

  it("keeps failed edits and does not show success-shaped feedback", async () => {
    rules = [initialRule]
    wrap(<Editor success={false} />)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    fireEvent.click(screen.getByRole("button", { name: copy.removeIban }))
    await screen.findByRole("alert")
    expect(screen.getByText("ES12 3456 7890")).toBeVisible()
    expect(mocks.toast).not.toHaveBeenCalled()
  })

  it("does not save or notify for an unchanged edit", () => {
    rules = [initialRule]
    wrap(<Editor />)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    fireEvent.click(screen.getByRole("button", { name: copy.editIban }))
    fireEvent.click(screen.getByRole("button", { name: copy.saveIban }))
    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.toast).not.toHaveBeenCalled()
  })

  it("preserves explicit empty account rules in the General settings save path", async () => {
    rules = [initialRule]
    wrap(<GeneralTab />)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    fireEvent.click(screen.getByRole("button", { name: copy.removeIban }))
    await waitFor(() =>
      expect(mocks.save).toHaveBeenCalledWith(
        expect.objectContaining({
          assets: { crypto, accounts: { exclusions: [] } },
        }),
        { silent: true },
      ),
    )
  })

  it("saves a pending General edit together with account changes and cancels the debounce", async () => {
    vi.useFakeTimers()
    rules = [initialRule]
    wrap(<GeneralTab />)
    fireEvent.click(
      screen.getByTestId("edit-mode-DRAFT").querySelector("input")!,
    )
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: copy.removeIban }))
    })
    expect(mocks.save).toHaveBeenCalledWith(
      expect.objectContaining({
        general: expect.objectContaining({ editMode: "DRAFT" }),
        assets: { crypto, accounts: { exclusions: [] } },
      }),
      { silent: true },
    )
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(mocks.save).toHaveBeenCalledTimes(1)
  })

  it("waits for an in-flight General save before persisting an account change", async () => {
    vi.useFakeTimers()
    let finish: (value: boolean) => void = () => {}
    mocks.save.mockImplementationOnce(
      () =>
        new Promise<boolean>(resolve => {
          finish = resolve
        }),
    )
    rules = [initialRule]
    wrap(<GeneralTab />)
    fireEvent.click(
      screen.getByTestId("edit-mode-DRAFT").querySelector("input")!,
    )
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })
    expect(mocks.save).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole("button", { name: /Accounts/ }))
    fireEvent.click(screen.getByRole("button", { name: copy.removeIban }))
    expect(mocks.save).toHaveBeenCalledTimes(1)
    await act(async () => {
      finish(true)
    })
    expect(mocks.save).toHaveBeenCalledTimes(2)
    expect(mocks.save).toHaveBeenLastCalledWith(
      expect.objectContaining({
        general: expect.objectContaining({ editMode: "DRAFT" }),
        assets: { crypto, accounts: { exclusions: [] } },
      }),
      { silent: true },
    )
  })
})
