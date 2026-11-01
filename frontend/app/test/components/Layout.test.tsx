import { StrictMode, useEffect, type ReactNode } from "react"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  Link,
  MemoryRouter,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom"
import { Layout } from "@/components/layout/Layout"
import { useLayoutScroll } from "@/context/LayoutScrollContext"
import {
  useNavigateWithReturn,
  useRestoreReturnScroll,
} from "@/hooks/useReturnNavigation"
import { returnScrollKey } from "@/lib/returnTo"

const { nativeMobile, openModal } = vi.hoisted(() => ({
  nativeMobile: vi.fn(() => false),
  openModal: vi.fn(() => false),
}))

vi.mock("@/components/layout/Sidebar", () => ({ Sidebar: () => null }))
vi.mock("@/components/layout/FloatingBottomNav", () => ({
  FloatingBottomNav: () => null,
}))
vi.mock("@/components/layout/StatusBarBlur", () => ({
  StatusBarBlur: () => null,
}))
vi.mock("@/components/ErrorBoundary", () => ({
  ErrorBoundary: ({ children }: { children: ReactNode }) => children,
}))
vi.mock("@/components/ui/Toast", () => ({ Toast: () => null }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    toast: null,
    hideToast: vi.fn(),
    showToast: vi.fn(),
  }),
}))
vi.mock("@/context/ModalRegistryContext", () => ({
  useModalRegistry: () => ({ dismissTop: vi.fn(), hasOpen: openModal }),
}))
vi.mock("@/i18n", () => ({ useI18n: () => ({ t: {} }) }))
vi.mock("@/lib/platform", () => ({
  getPlatformType: () => "WEB",
  isAndroid: () => false,
  isIOS: () => false,
  isNativeMobile: nativeMobile,
  isPWAStandalone: () => false,
}))
vi.mock("@/components/telemetry/TelemetryConsentDialog", () => ({
  TelemetryConsentDialog: () => null,
  useErrorReportingConsent: () => ({ enabled: false, refresh: vi.fn() }),
}))

const dashboardScroll = vi.fn()

function DashboardPage() {
  const { scrollRootRef } = useLayoutScroll()

  useEffect(() => {
    dashboardScroll(scrollRootRef.current?.scrollTop)
  }, [scrollRootRef])

  return <h1>Dashboard</h1>
}

function TransactionsPage({ ready }: { ready: boolean }) {
  const navigateWithReturn = useNavigateWithReturn("Transactions")
  useRestoreReturnScroll(ready)

  return (
    <>
      <Link to="/">Dashboard</Link>
      <Link to="/transactions?filter=income">Filter</Link>
      <button onClick={() => navigateWithReturn("/labels")}>Labels</button>
    </>
  )
}

function LabelsPage() {
  const navigate = useNavigate()
  return <button onClick={() => navigate(-1)}>Return</button>
}

function TestApp({ ready = true }: { ready?: boolean }) {
  return (
    <StrictMode>
      <MemoryRouter
        initialEntries={[{ pathname: "/transactions", key: "transactions" }]}
      >
        <Layout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route
              path="/transactions"
              element={<TransactionsPage ready={ready} />}
            />
            <Route path="/labels" element={<LabelsPage />} />
          </Routes>
        </Layout>
      </MemoryRouter>
    </StrictMode>
  )
}

function swipeRight(target: HTMLElement, startX = 10, vertical = false) {
  const start = { clientX: startX, clientY: 680 }
  const end = {
    clientX: vertical ? startX + 5 : window.innerWidth / 2,
    clientY: vertical ? 780 : 680,
  }
  fireEvent.touchStart(target, { touches: [start] })
  fireEvent.touchMove(target, { touches: [end] })
  fireEvent.touchEnd(target, { changedTouches: [end] })
}

describe.each([
  { viewport: "mobile", width: 390 },
  { viewport: "desktop", width: 1280 },
])("Layout scroll on $viewport", ({ width }) => {
  beforeEach(() => {
    vi.clearAllMocks()
    nativeMobile.mockReturnValue(false)
    openModal.mockReturnValue(false)
    vi.stubGlobal("innerWidth", width)
    sessionStorage.clear()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    sessionStorage.clear()
  })

  it("keeps the gesture target full-height with short page content", () => {
    render(<TestApp />)

    expect(screen.getByRole("main").firstElementChild).toHaveClass("min-h-full")
  })

  it("returns to the origin from a lower-screen native swipe and restores scroll", async () => {
    nativeMobile.mockReturnValue(true)
    render(<TestApp />)
    const scrollRoot = screen.getByRole("main")
    scrollRoot.scrollTop = 659
    fireEvent.click(screen.getByRole("button", { name: "Labels" }))
    const gestureRoot = scrollRoot.firstElementChild as HTMLElement

    swipeRight(gestureRoot)

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: "Dashboard" }),
      ).toBeInTheDocument()
      expect(scrollRoot.scrollTop).toBe(659)
    })
    expect(sessionStorage.getItem(returnScrollKey("transactions"))).toBeNull()
  })

  it.each([
    "a non-edge start",
    "a vertical swipe",
    "an open modal",
    "a horizontal scroller",
    "a web viewport",
  ])("does not navigate for %s", scenario => {
    nativeMobile.mockReturnValue(scenario !== "a web viewport")
    openModal.mockReturnValue(scenario === "an open modal")
    render(<TestApp />)
    fireEvent.click(screen.getByRole("button", { name: "Labels" }))
    const gestureRoot = screen.getByRole("main")
      .firstElementChild as HTMLElement
    const gestureContent = gestureRoot.lastElementChild as HTMLElement
    let target = gestureRoot

    if (scenario === "a horizontal scroller") {
      Object.defineProperties(gestureContent, {
        clientWidth: { configurable: true, value: 300 },
        scrollWidth: { configurable: true, value: 600 },
      })
      gestureContent.style.overflowX = "auto"
      target = gestureContent
    }

    swipeRight(
      target,
      scenario === "a non-edge start" ? 40 : 10,
      scenario === "a vertical swipe",
    )

    expect(gestureContent.style.transform).toBe("")
    expect(screen.getByRole("button", { name: "Return" })).toBeInTheDocument()
  })

  it("resets the shared container before the destination page effects", () => {
    render(<TestApp />)
    const scrollRoot = screen.getByRole("main")
    scrollRoot.scrollTop = 900

    fireEvent.click(screen.getByRole("link", { name: "Dashboard" }))

    expect(
      screen.getByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument()
    expect(screen.getByRole("main")).toBe(scrollRoot)
    expect(scrollRoot.scrollTop).toBe(0)
    expect(dashboardScroll).toHaveBeenLastCalledWith(0)
  })

  it("preserves the offset when only the query changes", () => {
    render(<TestApp />)
    const scrollRoot = screen.getByRole("main")
    scrollRoot.scrollTop = 600

    fireEvent.click(screen.getByRole("link", { name: "Filter" }))

    expect(screen.getByRole("main")).toBe(scrollRoot)
    expect(scrollRoot.scrollTop).toBe(600)
  })

  it("restores the saved offset when returning to the origin", () => {
    render(<TestApp />)
    const scrollRoot = screen.getByRole("main")
    scrollRoot.scrollTop = 659

    fireEvent.click(screen.getByRole("button", { name: "Labels" }))

    expect(scrollRoot.scrollTop).toBe(0)
    expect(sessionStorage.getItem(returnScrollKey("transactions"))).toBe("659")
    scrollRoot.scrollTop = 300

    fireEvent.click(screen.getByRole("button", { name: "Return" }))

    expect(screen.getByRole("main")).toBe(scrollRoot)
    expect(scrollRoot.scrollTop).toBe(659)
    expect(sessionStorage.getItem(returnScrollKey("transactions"))).toBeNull()
  })

  it("waits for return content and preserves restoration across query changes", () => {
    const { rerender } = render(<TestApp ready={false} />)
    const scrollRoot = screen.getByRole("main")
    scrollRoot.scrollTop = 659
    fireEvent.click(screen.getByRole("button", { name: "Labels" }))
    scrollRoot.scrollTop = 300

    fireEvent.click(screen.getByRole("button", { name: "Return" }))

    expect(scrollRoot.scrollTop).toBe(0)
    expect(sessionStorage.getItem(returnScrollKey("transactions"))).toBe("659")

    rerender(<TestApp ready />)

    expect(scrollRoot.scrollTop).toBe(659)
    expect(sessionStorage.getItem(returnScrollKey("transactions"))).toBeNull()

    fireEvent.click(screen.getByRole("link", { name: "Filter" }))

    expect(scrollRoot.scrollTop).toBe(659)
  })
})
