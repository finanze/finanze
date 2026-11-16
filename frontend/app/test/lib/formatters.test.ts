import { describe, expect, it } from "vitest"
import { lowercaseLabel } from "@/lib/formatters"

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
