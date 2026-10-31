import { cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { CountryFlag } from "@/components/CountryFlag"

afterEach(cleanup)

describe("CountryFlag", () => {
  it.each(["ES", "GB"])("renders the %s flag as an SVG", code => {
    const { container } = render(<CountryFlag code={code} />)

    expect(container.querySelector("svg")).not.toBeNull()
    expect(container.textContent).toBe("")
  })

  it("renders a globe for unsupported country codes", () => {
    const { container } = render(<CountryFlag code="ZZ" />)

    expect(container.querySelector("svg")).not.toBeNull()
    expect(container.textContent).toBe("")
  })
})
