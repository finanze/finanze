import { beforeEach, afterEach, describe, expect, it } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"
import { type ReactNode } from "react"
import { BottomNavProvider, useBottomNav } from "@/context/BottomNavContext"

const STORAGE_KEY = "finanze-bottom-nav"
const wrapper = ({ children }: { children: ReactNode }) => (
  <BottomNavProvider>{children}</BottomNavProvider>
)
const renderNav = () => renderHook(useBottomNav, { wrapper })

beforeEach(() => localStorage.clear())
afterEach(cleanup)

describe("BottomNavContext", () => {
  it("keeps today's defaults and persists a versioned local preference", () => {
    const { result } = renderNav()
    expect(result.current.bar).toEqual([
      "dashboard",
      "investments",
      "transactions",
      "calculations",
      "management",
      "entities",
    ])
    expect(result.current.menu).toEqual(["settings", "export"])
    expect(result.current.isCustomized).toBe(false)
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual({
      version: 1,
      bar: result.current.bar,
      menu: result.current.menu,
    })
  })

  it.each([
    "not json",
    "null",
    "[]",
    '{"version":2,"bar":[],"menu":[]}',
    '{"version":1,"bar":null,"menu":[]}',
  ])("recovers from invalid storage: %s", raw => {
    localStorage.setItem(STORAGE_KEY, raw)
    expect(renderNav().result.current.isCustomized).toBe(false)
  })

  it("dedupes, drops unavailable shortcuts, restores roots and fills a short bar", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        version: 1,
        bar: ["crypto", "crypto", "unknown", "market-forecast", 3],
        menu: ["crypto", "settings"],
      }),
    )
    const { result } = renderNav()
    expect(result.current.bar).toEqual([
      "crypto",
      "settings",
      "dashboard",
      "investments",
    ])
    expect(result.current.menu).toEqual([
      "transactions",
      "calculations",
      "management",
      "entities",
      "export",
    ])
  })

  it("puts excess bar items in the menu without duplicates", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        version: 1,
        bar: [
          "dashboard",
          "investments",
          "transactions",
          "calculations",
          "management",
          "entities",
          "banking",
          "crypto",
        ],
        menu: ["crypto", "settings", "export"],
      }),
    )
    const { result } = renderNav()
    expect(result.current.bar).toHaveLength(6)
    expect(result.current.menu).toEqual([
      "banking",
      "crypto",
      "settings",
      "export",
    ])
  })

  it("enforces the 4..6 limits even with repeated updates", () => {
    const { result } = renderNav()
    act(() => {
      result.current.moveToBar("settings")
      result.current.moveToMenu("calculations")
      result.current.moveToMenu("entities")
      result.current.moveToMenu("management")
      result.current.moveToMenu("unknown" as "dashboard")
    })
    expect(result.current.bar).toHaveLength(4)
    expect(result.current.menu).toEqual([
      "settings",
      "export",
      "calculations",
      "entities",
    ])
    act(() => {
      result.current.moveToBar("settings")
      result.current.moveToBar("export")
      result.current.moveToBar("calculations")
    })
    expect(result.current.bar).toHaveLength(6)
    expect(result.current.menu).toEqual(["calculations", "entities"])
  })

  it("adds shortcuts to a free bar slot or the menu and only removes menu shortcuts", () => {
    const { result } = renderNav()
    act(() => {
      result.current.addShortcut("banking")
      result.current.addShortcut("banking")
      result.current.addShortcut("market-forecast")
      result.current.removeShortcut("settings")
      result.current.moveToMenu("calculations")
      result.current.addShortcut("crypto")
      result.current.removeShortcut("crypto")
    })
    expect(result.current.bar).toContain("crypto")
    expect(result.current.menu).toEqual([
      "settings",
      "export",
      "banking",
      "calculations",
    ])
    act(() => result.current.removeShortcut("banking"))
    expect(result.current.menu).not.toContain("banking")
  })

  it("reorders only the same set, restores it on mount, and resets", () => {
    const { result, unmount } = renderNav()
    const reversed = [...result.current.bar].reverse()
    act(() => result.current.reorderBar(reversed))
    act(() => result.current.reorderMenu(["export", "settings"]))
    act(() => {
      result.current.reorderBar(["dashboard"])
      result.current.reorderMenu(["settings", "settings"])
      result.current.reorderMenu(["settings", "crypto"])
    })
    expect(result.current.bar).toEqual(reversed)
    expect(result.current.menu).toEqual(["export", "settings"])
    expect(result.current.isCustomized).toBe(true)
    unmount()
    const restored = renderNav()
    expect(restored.result.current.bar).toEqual(reversed)
    act(() => restored.result.current.reset())
    expect(restored.result.current.isCustomized).toBe(false)
  })
})
