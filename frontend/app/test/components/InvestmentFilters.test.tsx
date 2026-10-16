import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { InvestmentFilters } from "@/components/InvestmentFilters"

vi.mock("@/i18n", () => ({
  useI18n: () => ({
    t: {
      transactions: {
        clear: "Clear",
        filters: "Filters",
        selectEntities: "Select entities",
      },
      walletManagement: { walletFilterPlaceholder: "Select wallet" },
    },
  }),
}))

vi.mock("@/components/EntitySelector", () => ({
  EntitySelector: () => <div data-testid="entity-selector" />,
}))

afterEach(cleanup)

describe("InvestmentFilters", () => {
  it("keeps the clear filters button by default", () => {
    render(
      <InvestmentFilters
        filteredEntities={[]}
        selectedEntities={["entity"]}
        onEntitiesChange={vi.fn()}
        showWalletFilter={false}
      />,
    )

    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy()
  })

  it("can hide the clear filters button", () => {
    render(
      <InvestmentFilters
        filteredEntities={[]}
        selectedEntities={["entity"]}
        onEntitiesChange={vi.fn()}
        showWalletFilter={false}
        showClearFilters={false}
      />,
    )

    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull()
  })
})
