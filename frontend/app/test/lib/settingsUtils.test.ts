import { describe, expect, it } from "vitest"
import { stripEmptySheetsGlobals } from "@/lib/settingsUtils"

describe("stripEmptySheetsGlobals", () => {
  it("removes empty globals from import and export settings", () => {
    const settings = {
      labeling: { external: { enabled: true } },
      export: { sheets: { globals: {}, transactions: [{ range: "A1:B2" }] } },
      importing: { sheets: { globals: {}, position: [{ range: "C1:D2" }] } },
    }

    expect(stripEmptySheetsGlobals(settings)).toEqual({
      labeling: { external: { enabled: true } },
      export: { sheets: { transactions: [{ range: "A1:B2" }] } },
      importing: { sheets: { position: [{ range: "C1:D2" }] } },
    })
  })

  it("preserves configured globals and labeling-only settings", () => {
    const configured = {
      export: { sheets: { globals: { spreadsheetId: "sheet-id" } } },
    }
    const labelingOnly = { labeling: { external: { enabled: true } } }

    expect(stripEmptySheetsGlobals(configured)).toEqual(configured)
    expect(stripEmptySheetsGlobals(labelingOnly)).toEqual(labelingOnly)
  })
})
