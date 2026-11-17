import { describe, expect, it } from "vitest"
import { formatDate, lowercaseLabel } from "@/lib/formatters"

describe("formatDate", () => {
  const date = "2024-02-05T12:00:00"

  it("uses an abbreviated Portuguese month in the Spanish compact layout", () => {
    expect(formatDate(date, "pt-PT")).toBe("5 fev. 2024")
    expect(formatDate(date, "es-ES")).toBe("5 feb 2024")
  })

  it.each([
    [{ day: "numeric", month: "short" }, "5 fev."],
    [{ month: "short", year: "2-digit" }, "fev. 24"],
    [{ month: "short", year: "numeric" }, "fev. 2024"],
    [{ weekday: "short", day: "numeric", month: "short" }, "segunda, 5 fev."],
  ] satisfies [Intl.DateTimeFormatOptions, string][])(
    "keeps abbreviated month names with %j",
    (options, expected) => {
      expect(formatDate(new Date(date), "pt-PT", options)).toBe(expected)
    },
  )

  it("uses the requested time zone for both the date and month name", () => {
    expect(
      formatDate("2024-02-01T00:30:00Z", "pt-PT", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "America/New_York",
      }),
    ).toBe("31 jan. 2024")
  })

  it.each(["en-US", "es-ES", "it-IT", "de-DE", "fr-FR"])(
    "preserves native compact formatting in %s",
    locale => {
      expect(formatDate(date, locale)).toBe(
        new Intl.DateTimeFormat(locale, {
          day: "numeric",
          month: "short",
          year: "numeric",
        }).format(new Date(date)),
      )
    },
  )

  it.each([
    [{ dateStyle: "long" }, "5 de fevereiro de 2024"],
    [{ day: "2-digit", month: "2-digit", year: "numeric" }, "05/02/2024"],
  ] satisfies [Intl.DateTimeFormatOptions, string][])(
    "preserves explicit long or numeric Portuguese dates with %j",
    (options, expected) => {
      expect(formatDate(date, "pt-PT", options)).toBe(expected)
    },
  )
})

describe("lowercaseLabel", () => {
  it.each(["en-US", "es-ES", "it-IT", undefined])(
    "lowercases labels in %s",
    locale => {
      expect(lowercaseLabel("Funds", locale)).toBe("funds")
    },
  )

  it("keeps noun capitalization in German", () => {
    expect(lowercaseLabel("Fonds", "de-DE")).toBe("Fonds")
  })
})
