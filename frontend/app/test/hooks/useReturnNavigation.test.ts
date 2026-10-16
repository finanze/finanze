import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useRestoreReturnScroll } from "@/hooks/useReturnNavigation"
import { returnScrollKey } from "@/lib/returnTo"

const { scrollRootRef } = vi.hoisted(() => ({
  scrollRootRef: { current: null as HTMLElement | null },
}))

vi.mock("react-router-dom", () => ({
  useLocation: () => ({ key: "origin" }),
}))

vi.mock("@/context/LayoutScrollContext", () => ({
  useLayoutScroll: () => ({ scrollRootRef }),
}))

describe("useRestoreReturnScroll", () => {
  const storageKey = returnScrollKey("origin")
  const observe = vi.fn()
  const disconnect = vi.fn()
  let resize: () => void
  let availableOffset: number
  let currentOffset: number

  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    availableOffset = 1000
    currentOffset = 0
    const scrollRoot = document.createElement("main")
    scrollRoot.appendChild(document.createElement("div"))
    Object.defineProperty(scrollRoot, "scrollTop", {
      get: () => currentOffset,
      set: (offset: number) => {
        currentOffset = Math.min(offset, availableOffset)
      },
    })
    scrollRootRef.current = scrollRoot
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback: () => void) {
          resize = callback
        }
        observe = observe
        disconnect = disconnect
      },
    )
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    sessionStorage.clear()
  })

  it("restores a reachable offset immediately", () => {
    sessionStorage.setItem(storageKey, "659")
    renderHook(() => useRestoreReturnScroll(true))
    expect(currentOffset).toBe(659)
    expect(sessionStorage.getItem(storageKey)).toBeNull()
    expect(observe).not.toHaveBeenCalled()
  })

  it("keeps a clamped offset until the content grows", () => {
    availableOffset = 533
    sessionStorage.setItem(storageKey, "659")
    renderHook(() => useRestoreReturnScroll(true))
    expect(currentOffset).toBe(533)
    expect(sessionStorage.getItem(storageKey)).toBe("659")
    expect(observe).toHaveBeenCalledWith(
      scrollRootRef.current?.firstElementChild,
    )
    availableOffset = 700
    act(() => resize())
    expect(currentOffset).toBe(659)
    expect(sessionStorage.getItem(storageKey)).toBeNull()
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it("waits for the page to be ready", () => {
    sessionStorage.setItem(storageKey, "659")
    const { rerender } = renderHook(
      ({ ready }) => useRestoreReturnScroll(ready),
      { initialProps: { ready: false } },
    )
    expect(currentOffset).toBe(0)
    expect(sessionStorage.getItem(storageKey)).toBe("659")
    rerender({ ready: true })
    expect(currentOffset).toBe(659)
    expect(sessionStorage.getItem(storageKey)).toBeNull()
  })

  it("disconnects a pending observer on unmount", () => {
    availableOffset = 533
    sessionStorage.setItem(storageKey, "659")
    const { unmount } = renderHook(() => useRestoreReturnScroll(true))
    unmount()
    expect(disconnect).toHaveBeenCalledOnce()
  })
})
