import { beforeEach, afterEach, describe, expect, it } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react"
import { BottomNavCard } from "@/components/settings/BottomNavCard"
import { BottomNavProvider } from "@/context/BottomNavContext"
import { I18nProvider } from "@/i18n"

function resize(width: number) {
  act(() => {
    window.innerWidth = width
    window.dispatchEvent(new Event("resize"))
  })
}

function renderCard() {
  return render(
    <I18nProvider>
      <BottomNavProvider>
        <BottomNavCard />
      </BottomNavProvider>
    </I18nProvider>,
  )
}

beforeEach(() => {
  localStorage.clear()
  resize(390)
})
afterEach(cleanup)

describe("BottomNavCard", () => {
  it("is only visible at the same widths as the floating bar", () => {
    resize(768)
    renderCard()
    expect(screen.queryByTestId("bottom-nav-settings")).not.toBeInTheDocument()
    resize(767)
    expect(
      screen.getByRole("heading", { name: "Bottom bar" }),
    ).toBeInTheDocument()
    resize(1024)
    expect(screen.queryByTestId("bottom-nav-settings")).not.toBeInTheDocument()
  })

  it("keeps More fixed and disables adding at six bar items", () => {
    renderCard()
    expect(screen.getByRole("status")).toHaveTextContent("6/6")
    expect(
      screen.getByRole("button", { name: "Move Settings to bar" }),
    ).toBeDisabled()
    expect(screen.getByLabelText("More stays at the end")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Reorder More" }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Reset to default" }),
    ).not.toBeInTheDocument()
  })

  it("moves pages both ways and enforces four as the minimum", () => {
    renderCard()
    fireEvent.click(
      screen.getByRole("button", { name: "Move Calculations to menu" }),
    )
    fireEvent.click(
      screen.getByRole("button", { name: "Move Integrations to menu" }),
    )
    expect(screen.getByRole("status")).toHaveTextContent("4/6")
    for (const button of within(
      screen.getByRole("region", { name: "In the bar" }),
    ).getAllByRole("button", { name: /^Move / }))
      expect(button).toBeDisabled()
    fireEvent.click(
      screen.getByRole("button", { name: "Move Settings to bar" }),
    )
    expect(screen.getByRole("status")).toHaveTextContent("5/6")
    expect(
      within(screen.getByRole("region", { name: "In the bar" })).getByText(
        "Settings",
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Remove Settings shortcut" }),
    ).not.toBeInTheDocument()
  })

  it("adds a subpage to a free slot and removes it through the menu", () => {
    renderCard()
    fireEvent.click(
      screen.getByRole("button", { name: "Move Calculations to menu" }),
    )
    fireEvent.click(screen.getByRole("button", { name: "Add shortcut" }))
    fireEvent.click(screen.getByRole("button", { name: "Add Crypto shortcut" }))
    expect(
      within(screen.getByRole("region", { name: "In the bar" })).getByText(
        "Crypto",
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Remove Crypto shortcut" }),
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Move Crypto to menu" }))
    fireEvent.click(
      screen.getByRole("button", { name: "Remove Crypto shortcut" }),
    )
    expect(
      screen.getByRole("button", { name: "Add Crypto shortcut" }),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId("bottom-nav-row-crypto"),
    ).not.toBeInTheDocument()
  })

  it("adds to the menu when full, filters unavailable features, and resets", () => {
    renderCard()
    fireEvent.click(screen.getByRole("button", { name: "Add shortcut" }))
    expect(
      screen.queryByRole("button", { name: /Add Market Forecast/ }),
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Add Crypto shortcut" }))
    expect(
      within(
        screen.getByRole("region", { name: "In the More menu" }),
      ).getByText("Crypto"),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }))
    expect(
      screen.queryByTestId("bottom-nav-row-crypto"),
    ).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("6/6")
  })

  it("supports keyboard reordering of both lists and persists immediately", () => {
    renderCard()
    const bar = screen.getByRole("region", { name: "In the bar" })
    fireEvent.keyDown(
      screen.getByRole("button", { name: "Reorder Investments" }),
      { key: "ArrowUp" },
    )
    expect(within(bar).getAllByRole("listitem")[0]).toHaveTextContent(
      "Investments",
    )
    fireEvent.keyDown(
      screen.getByRole("button", { name: "Reorder Settings" }),
      { key: "ArrowDown" },
    )
    const saved = JSON.parse(localStorage.getItem("finanze-bottom-nav")!)
    expect(saved.bar[0]).toBe("investments")
    expect(saved.menu).toEqual(["export", "settings"])
  })
})
