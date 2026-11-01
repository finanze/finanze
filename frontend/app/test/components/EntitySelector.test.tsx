import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { EntitySelector } from "@/components/EntitySelector"
import { EntityOrigin, EntityType, type Entity, type Feature } from "@/types"

const featureValues: Record<Feature, string> = {
  POSITION: "",
  AUTO_CONTRIBUTIONS: "",
  TRANSACTIONS: "",
  HISTORIC: "",
}

const selectedEntity = {
  id: "selected-entity",
  name: "Selected entity",
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.NATIVE,
  natural_id: "selected-entity",
  features: [],
  last_fetch: featureValues,
  virtual_features: featureValues,
} satisfies Entity

vi.mock("@/i18n", () => ({
  useI18n: () => ({
    t: {
      common: { clear: "Clear" },
      transactions: { selectEntities: "Select entities" },
    },
  }),
}))

afterEach(cleanup)

describe("EntitySelector", () => {
  it("clears all selected entity ids", () => {
    const onSelectionChange = vi.fn()

    render(
      <EntitySelector
        entities={[selectedEntity]}
        selectedEntityIds={["selected-entity"]}
        onSelectionChange={onSelectionChange}
      />,
    )

    const clearButton = screen.getByRole("button", { name: "Clear" })
    const count = screen.getByText("1")
    expect(clearButton.contains(count)).toBe(true)

    fireEvent.click(clearButton)

    expect(onSelectionChange).toHaveBeenCalledWith([])
  })

  it("does not show the clear button without a selection", () => {
    render(
      <EntitySelector
        entities={[]}
        selectedEntityIds={[]}
        onSelectionChange={vi.fn()}
      />,
    )

    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull()
  })
})
