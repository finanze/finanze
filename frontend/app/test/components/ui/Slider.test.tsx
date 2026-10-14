import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { Slider, type SliderScale } from "@/components/ui/Slider"
import en from "@/i18n/locales/en.json"

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))

afterEach(() => {
  cleanup()
})

function Harness({
  initial,
  min,
  max,
  step,
  unit,
  scale,
  onCommit,
}: {
  initial: number | null
  min: number
  max: number
  step?: number
  unit?: string
  scale?: SliderScale
  onCommit?: (value: number) => void
}) {
  const [value, setValue] = useState<number | null>(initial)
  return (
    <Slider
      value={value}
      onValueChange={setValue}
      onValueCommit={onCommit}
      min={min}
      max={max}
      step={step}
      unit={unit}
      scale={scale}
      showLimits
      aria-label="slider"
    />
  )
}

const thumb = () => screen.getByRole("slider")

describe("Slider", () => {
  it("steps linearly with decimals and unit", () => {
    render(<Harness initial={3.5} min={0} max={10} step={0.25} unit="%" />)
    expect(thumb()).toHaveAttribute("aria-valuetext", "3.50 %")

    fireEvent.keyDown(thumb(), { key: "ArrowRight" })
    expect(thumb()).toHaveAttribute("aria-valuenow", "3.75")
    expect(thumb()).toHaveAttribute("aria-valuetext", "3.75 %")

    fireEvent.keyDown(thumb(), { key: "End" })
    expect(thumb()).toHaveAttribute("aria-valuenow", "10")
    fireEvent.keyDown(thumb(), { key: "Home" })
    expect(thumb()).toHaveAttribute("aria-valuenow", "0")
    expect(screen.getAllByText("10.00 %")).not.toHaveLength(0)
  })

  it("shows a placeholder when there is no value", () => {
    render(<Harness initial={null} min={1} max={40} unit="years" />)
    expect(thumb()).toHaveAttribute("aria-valuetext", "— years")
  })

  it("maps values exponentially and always advances at least one step", () => {
    const onCommit = vi.fn()
    const { container } = render(
      <Harness
        initial={119203}
        min={0}
        max={1000000}
        step={1000}
        scale="exponential"
        onCommit={onCommit}
      />,
    )
    const range = container.querySelector(
      "[data-orientation=horizontal] > span > span",
    ) as HTMLElement
    expect(parseFloat(range.style.right)).toBeCloseTo(50, 0)

    fireEvent.keyDown(thumb(), { key: "Home" })
    expect(thumb()).toHaveAttribute("aria-valuenow", "0")

    fireEvent.keyDown(thumb(), { key: "ArrowRight" })
    expect(thumb()).toHaveAttribute("aria-valuenow", "1000")
    expect(onCommit).toHaveBeenLastCalledWith(1000)

    fireEvent.keyDown(thumb(), { key: "End" })
    expect(thumb()).toHaveAttribute("aria-valuenow", "1000000")
    fireEvent.keyDown(thumb(), { key: "ArrowLeft" })
    const nearTop = Number(thumb().getAttribute("aria-valuenow"))
    expect(1000000 - nearTop).toBeGreaterThan(10000)
  })
})
