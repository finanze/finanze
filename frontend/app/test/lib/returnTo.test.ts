import { describe, expect, it } from "vitest"

import { readReturnTo, returnScrollKey } from "@/lib/returnTo"
import { canNavigateBack } from "@/lib/mobile/backNavigation"

describe("readReturnTo", () => {
  it("returns the origin when the state is valid", () => {
    expect(
      readReturnTo({
        returnTo: {
          path: "/management/cashflow?period=lastMonth",
          label: "Activity",
        },
      }),
    ).toEqual({
      path: "/management/cashflow?period=lastMonth",
      label: "Activity",
    })
  })

  it("ignores missing or malformed state", () => {
    expect(readReturnTo(null)).toBeNull()
    expect(readReturnTo(undefined)).toBeNull()
    expect(readReturnTo("returnTo")).toBeNull()
    expect(readReturnTo({})).toBeNull()
    expect(readReturnTo({ returnTo: "/management" })).toBeNull()
    expect(
      readReturnTo({ returnTo: { path: 42, label: "Activity" } }),
    ).toBeNull()
    expect(readReturnTo({ returnTo: { path: "/management" } })).toBeNull()
  })

  it("rejects paths that are not app-relative", () => {
    expect(
      readReturnTo({ returnTo: { path: "//evil.com", label: "x" } }),
    ).toBeNull()
    expect(
      readReturnTo({ returnTo: { path: "https://evil.com", label: "x" } }),
    ).toBeNull()
    expect(
      readReturnTo({ returnTo: { path: "management", label: "x" } }),
    ).toBeNull()
  })

  it("builds a scroll key per history entry", () => {
    expect(returnScrollKey("abc")).toBe("returnScroll:abc")
  })
})

describe("canNavigateBack", () => {
  it("keeps top-level pages non-navigable without an origin", () => {
    expect(canNavigateBack("/transactions")).toBe(false)
  })

  it("allows going back when an origin is present", () => {
    expect(
      canNavigateBack("/transactions", {
        returnTo: { path: "/management/cashflow", label: "Activity" },
      }),
    ).toBe(true)
  })
})
