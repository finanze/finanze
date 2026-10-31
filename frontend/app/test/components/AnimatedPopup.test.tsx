import { useState } from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AnimatedPopup } from "../../src/components/ui/AnimatedPopup"

function AnimatedPopupHarness() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button type="button" onClick={() => setOpen(value => !value)}>
        Toggle popup
      </button>
      <AnimatedPopup open={open} data-testid="popup">
        Popup content
      </AnimatedPopup>
    </>
  )
}

describe("AnimatedPopup", () => {
  it("keeps the popup present until its exit animation completes", async () => {
    render(<AnimatedPopupHarness />)

    fireEvent.click(screen.getByRole("button", { name: "Toggle popup" }))
    expect(screen.getByTestId("popup")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Toggle popup" }))
    expect(screen.getByTestId("popup")).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByTestId("popup")).not.toBeInTheDocument()
    })
  })
})
