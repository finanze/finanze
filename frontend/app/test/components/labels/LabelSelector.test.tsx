import { useState } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { LabelSelector } from "@/components/labels/LabelSelector"
import { LabelCategory, type Label } from "@/types/labeling"

const labels: Label[] = [
  { id: "food", name: "Food", category: LabelCategory.EXPENSE },
  { id: "home", name: "Home", category: LabelCategory.EXPENSE },
  { id: "transfer", name: "Transfer", category: LabelCategory.EXCLUDED },
]

vi.mock("@/context/LabelsContext", () => ({
  useLabels: () => ({
    labels,
    getLabelName: (label: Label) => label.name,
  }),
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({
    t: {
      labels: { searchLabels: "Search labels" },
      common: { noOptionsFound: "No options found" },
    },
  }),
}))

function Picker({
  mode,
  options,
}: {
  mode?: "single" | "multiple"
  options?: Label[]
}) {
  const [value, setValue] = useState(["food"])
  return (
    <LabelSelector
      value={value}
      onChange={setValue}
      mode={mode}
      options={options}
    />
  )
}

beforeEach(() => cleanup())

describe("LabelSelector", () => {
  it("replaces and clears the optional single selection", () => {
    render(<Picker mode="single" />)
    fireEvent.click(screen.getByRole("button", { name: "Home" }))
    expect(screen.getByRole("button", { name: "Food" })).toHaveAttribute(
      "aria-pressed",
      "false",
    )
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    fireEvent.click(screen.getByRole("button", { name: "Home" }))
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute(
      "aria-pressed",
      "false",
    )
  })

  it("keeps append and remove behavior by default", () => {
    render(<Picker />)
    fireEvent.click(screen.getByRole("button", { name: "Home" }))
    expect(screen.getByRole("button", { name: "Food" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    fireEvent.click(screen.getByRole("button", { name: "Food" }))
    expect(screen.getByRole("button", { name: "Food" })).toHaveAttribute(
      "aria-pressed",
      "false",
    )
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })

  it("searches only within the supplied eligible options", () => {
    render(
      <Picker
        mode="single"
        options={labels.filter(
          label => label.category !== LabelCategory.EXCLUDED,
        )}
      />,
    )
    expect(
      screen.queryByRole("button", { name: "Transfer" }),
    ).not.toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText("Search labels"), {
      target: { value: "home" },
    })
    expect(
      screen.queryByRole("button", { name: "Food" }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument()
  })

  it("does not change a disabled selection", () => {
    const onChange = vi.fn()
    render(
      <LabelSelector
        value={["food"]}
        onChange={onChange}
        mode="single"
        disabled
      />,
    )
    fireEvent.click(screen.getByRole("button", { name: "Home" }))
    expect(onChange).not.toHaveBeenCalled()
  })
})
