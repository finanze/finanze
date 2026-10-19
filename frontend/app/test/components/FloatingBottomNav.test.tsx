import { beforeEach, afterEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { MemoryRouter, useLocation } from "react-router-dom"
import { I18nProvider } from "@/i18n"
import { BottomNavProvider } from "@/context/BottomNavContext"
import { FloatingBottomNav } from "@/components/layout/FloatingBottomNav"
import { BottomNavCard } from "@/components/settings/BottomNavCard"

const scroll = vi.hoisted(() => ({ scrolling: false }))

vi.mock("@/context/LayoutScrollContext", () => ({
  useLayoutScroll: () => ({
    scrolling: scroll.scrolling,
    atTop: true,
    atBottom: false,
  }),
}))
vi.mock("@/context/BackupAlertContext", () => ({
  useBackupAlert: () => ({ alertColor: "red" }),
}))

function Location() {
  return <output>{useLocation().pathname}</output>
}

function renderNav(
  path = "/",
  bar?: string[],
  menu?: string[],
  editing = false,
) {
  if (bar)
    localStorage.setItem(
      "finanze-bottom-nav",
      JSON.stringify({ version: 1, bar, menu }),
    )
  const tree = () => (
    <I18nProvider>
      <MemoryRouter initialEntries={[path]}>
        <BottomNavProvider>
          {editing && <BottomNavCard />}
          <FloatingBottomNav />
          <Location />
        </BottomNavProvider>
      </MemoryRouter>
    </I18nProvider>
  )
  const view = render(tree())
  return { ...view, update: () => view.rerender(tree()) }
}

beforeEach(() => {
  localStorage.clear()
  scroll.scrolling = false
  window.innerWidth = 390
})
afterEach(cleanup)

describe("FloatingBottomNav", () => {
  it("restores buttons when collapse is interrupted by an immediate expansion", async () => {
    const view = renderNav()
    scroll.scrolling = true
    view.update()
    expect(screen.getByTestId("floating-bottom-nav")).toHaveAttribute(
      "data-state",
      "collapsed",
    )
    scroll.scrolling = false
    view.update()
    expect(screen.getByTestId("floating-bottom-nav")).toHaveAttribute(
      "data-state",
      "expanded",
    )
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "More" })).toBeVisible(),
    )
  })

  it("keeps the live bar expanded while customizing, even during scroll", async () => {
    scroll.scrolling = true
    renderNav("/", undefined, undefined, true)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "More" })).toBeVisible(),
    )
    fireEvent.click(
      screen.getByRole("button", { name: "Move Calculations to menu" }),
    )
    expect(screen.getByRole("button", { name: "More" })).toBeVisible()
    expect(
      screen.queryByRole("button", { name: "Calculations" }),
    ).not.toBeInTheDocument()
  })

  it("renders a custom order, keeps More last and navigates from the menu", async () => {
    renderNav(
      "/",
      ["transactions", "dashboard", "crypto", "management"],
      ["settings", "export", "investments", "calculations", "entities"],
    )
    expect(
      screen
        .getAllByRole("button")
        .map(button => button.getAttribute("aria-label")),
    ).toEqual(["Transactions", "Summary", "Crypto", "My Money", "More"])
    fireEvent.click(screen.getByRole("button", { name: "More" }))
    fireEvent.click(await screen.findByRole("button", { name: "Calculations" }))
    expect(screen.getByRole("status")).toHaveTextContent("/calculations")
    expect(screen.getByRole("button", { name: "More" })).toHaveAttribute(
      "aria-current",
      "page",
    )
  })

  it.each([
    ["/investments/crypto", "Crypto"],
    ["/real-estate/123", "Real Estate"],
    ["/management/recurring", "My Money"],
    ["/banking", "Investments"],
  ])(
    "highlights the most specific available tab for %s",
    async (path, label) => {
      renderNav(
        path,
        ["investments", "crypto", "real-estate", "management"],
        [
          "dashboard",
          "transactions",
          "calculations",
          "entities",
          "settings",
          "export",
        ],
      )
      await waitFor(() =>
        expect(screen.getByRole("button", { name: label })).toHaveAttribute(
          "aria-current",
          "page",
        ),
      )
    },
  )

  it("highlights More for a selected menu subpage instead of its parent tab", () => {
    renderNav(
      "/investments/crypto",
      ["dashboard", "investments", "transactions", "management"],
      ["crypto", "settings", "export", "calculations", "entities"],
    )
    expect(screen.getByRole("button", { name: "More" })).toHaveAttribute(
      "aria-current",
      "page",
    )
  })

  it("moves the backup alert dot to Settings when it is in the bar", () => {
    renderNav(
      "/settings",
      ["settings", "dashboard", "investments", "transactions"],
      ["export", "calculations", "management", "entities"],
    )
    expect(
      screen
        .getByRole("button", { name: "Settings" })
        .querySelector(".bg-red-500"),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "More" }).querySelector(".bg-red-500"),
    ).not.toBeInTheDocument()
  })

  it("marks only the most specific current page inside the menu", async () => {
    renderNav(
      "/management/cashflow",
      ["dashboard", "investments", "transactions", "calculations"],
      ["management", "management-cashflow", "entities", "settings", "export"],
    )
    fireEvent.click(screen.getByRole("button", { name: "More" }))
    expect(
      await screen.findByRole("button", { name: "Activity" }),
    ).toHaveAttribute("aria-current", "page")
    expect(
      screen.getByRole("button", { name: "My Money" }),
    ).not.toHaveAttribute("aria-current")
  })
})
