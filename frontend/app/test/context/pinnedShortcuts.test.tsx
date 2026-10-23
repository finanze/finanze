import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { act, renderHook, cleanup } from "@testing-library/react"
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

  it("adds cashflow to existing pins when missing", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(["crypto", "management-pending"]),
    )
    const { result } = renderPinned()
    expect(result.current.pinnedShortcuts).toEqual([
      "crypto",
      "management-pending",
      "management-cashflow",
    ])
  })

  it("does not restore cashflow after a user unpins it", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(["crypto"]))
    const firstRender = renderPinned()

    act(() => {
      firstRender.result.current.unpin("management-cashflow")
    })
    firstRender.unmount()

    const secondRender = renderPinned()
    expect(secondRender.result.current.pinnedShortcuts).toEqual(["crypto"])
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
