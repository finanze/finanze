import { afterEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { I18nProvider, useI18n, type Locale } from "@/i18n"
import en from "@/i18n/locales/en.json"
import pt from "@/i18n/locales/pt.json"
import fr from "@/i18n/locales/fr.json"
import { DatePicker } from "@/components/ui/DatePicker"
import { LoginQuickSettings } from "@/components/ui/LoginQuickSettings"

vi.mock("@/context/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", setThemeMode: vi.fn() }),
}))

afterEach(() => {
  cleanup()
  localStorage.clear()
})

function checkCatalog(source: unknown, translated: unknown, path = ""): void {
  expect(Array.isArray(translated), path).toBe(Array.isArray(source))
  expect(typeof translated, path).toBe(typeof source)
  if (typeof source === "string" && typeof translated === "string") {
    const placeholders = (value: string) =>
      (value.match(/\{\{[^}]+\}\}|\{[^}]+\}/g) ?? []).sort()
    expect(placeholders(translated), path).toEqual(placeholders(source))
    if (
      path.startsWith(".settings.integration.") &&
      (path.endsWith(".url") || path.endsWith(".type"))
    ) {
      expect(translated, path).toBe(source)
    }
    return
  }
  if (
    source &&
    translated &&
    typeof source === "object" &&
    typeof translated === "object"
  ) {
    const sourceEntries = Object.entries(source)
    const translatedEntries = Object.entries(translated)
    expect(
      translatedEntries.map(([key]) => key),
      path,
    ).toEqual(sourceEntries.map(([key]) => key))
    const translatedValues = new Map(translatedEntries)
    for (const [key, value] of sourceEntries) {
      checkCatalog(value, translatedValues.get(key), `${path}.${key}`)
    }
  }
}

function LocaleProbe() {
  const { locale, t, changeLocale } = useI18n()
  return (
    <>
      <output>{locale}</output>
      <span>{t.common.settings}</span>
      <button onClick={() => changeLocale("pt-PT")}>Portuguese</button>
      <button onClick={() => changeLocale("fr-FR")}>French</button>
      <DatePicker value="2024-03-15" />
      <DatePicker />
    </>
  )
}

describe("Portuguese and French locales", () => {
  it.each([
    ["Portuguese", pt],
    ["French", fr],
  ])(
    "preserves the English catalog structure and placeholders in %s",
    (_, catalog) => {
      checkCatalog(en, catalog)
    },
  )

  it.each([
    ["pt-PT", "Portuguese", pt, "15 de março de 2024", /^março 2024$/i],
    ["fr-FR", "French", fr, "15 mars 2024", /^mars 2024$/i],
  ] as const)(
    "selects and restores %s with localized dates",
    async (locale: Locale, label, catalog, formattedDate, monthLabel) => {
      const { unmount } = render(
        <I18nProvider>
          <LocaleProbe />
        </I18nProvider>,
      )
      fireEvent.click(screen.getByRole("button", { name: label }))
      expect(localStorage.getItem("locale")).toBe(locale)
      expect(screen.getByText(catalog.common.settings)).toBeInTheDocument()
      expect(screen.getByText(formattedDate)).toBeInTheDocument()
      expect(
        screen.getByText(catalog.transactions.form.pickDate),
      ).toBeInTheDocument()
      fireEvent.click(screen.getByRole("button", { name: formattedDate }))
      expect(await screen.findByText(monthLabel)).toBeInTheDocument()

      unmount()
      render(
        <I18nProvider>
          <LocaleProbe />
        </I18nProvider>,
      )
      await waitFor(() => expect(screen.getByText(locale)).toBeInTheDocument())
      expect(screen.getByText(formattedDate)).toBeInTheDocument()
    },
  )

  it.each([
    ["PT", "pt-PT"],
    ["FR", "fr-FR"],
  ])("offers %s on the login screen", async (label, locale) => {
    render(
      <I18nProvider>
        <LoginQuickSettings />
      </I18nProvider>,
    )
    fireEvent.click(screen.getAllByRole("button")[0])
    fireEvent.click(await screen.findByRole("button", { name: label }))
    expect(localStorage.getItem("locale")).toBe(locale)
  })
})
