import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { renderHook, cleanup } from "@testing-library/react"
import { type ReactNode } from "react"
import {
  PinnedShortcutsProvider,
  usePinnedShortcuts,
} from "@/context/PinnedShortcutsContext"

const STORAGE_KEY = "finanze-pinned-assets"

const wrapper = ({ children }: { children: ReactNode }) => (
  <PinnedShortcutsProvider>{children}</PinnedShortcutsProvider>
)

function renderPinned() {
  return renderHook(() => usePinnedShortcuts(), { wrapper })
}

describe("PinnedShortcutsContext", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    cleanup()
  })

  it("pins banking and cashflow by default for new users", () => {
    const { result } = renderPinned()
    expect(result.current.pinnedShortcuts).toEqual([
      "banking",
      "management-cashflow",
    ])
  })

  it("keeps existing user pins untouched", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(["crypto", "management-pending"]),
    )
    const { result } = renderPinned()
    expect(result.current.pinnedShortcuts).toEqual([
      "crypto",
      "management-pending",
    ])
  })

  it("maps legacy shortcut ids to their new pages and dedupes", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([
        "management-auto-contributions",
        "management-recurring",
        "management-labels",
        "unknown-id",
      ]),
    )
    const { result } = renderPinned()
    expect(result.current.pinnedShortcuts).toEqual([
      "management-recurring",
      "management-cashflow",
    ])
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual([
      "management-recurring",
      "management-cashflow",
    ])
  })
})
