import { useState } from "react"
import { beforeEach, describe, expect, it } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import {
  TagInput,
  mergeTags,
  type TagSeparator,
} from "@/components/ui/TagInput"

function Harness({
  initial = [],
  separators,
  maxItems,
}: {
  initial?: string[]
  separators?: TagSeparator[]
  maxItems?: number
}) {
  const [values, setValues] = useState(initial)
  const [draft, setDraft] = useState("")
  return (
    <TagInput
      values={values}
      onChange={setValues}
      draft={draft}
      onDraftChange={setDraft}
      separators={separators}
      maxItems={maxItems}
      removeLabel={value => `Remove ${value}`}
      testId="tags"
    />
  )
}

const chips = () =>
  screen.queryAllByTestId("tag-chip").map(chip => chip.textContent)

const input = () => screen.getByTestId("tags") as HTMLInputElement

beforeEach(() => cleanup())

describe("mergeTags", () => {
  it("trims, skips blanks and ignores case and accent duplicates", () => {
    expect(
      mergeTags(["Café"], [" cafe ", "", "  ", "LIDL", "lidl", "Aldi"]),
    ).toEqual(["Café", "LIDL", "Aldi"])
  })

  it("stops at the maximum number of items", () => {
    expect(mergeTags(["a"], ["b", "c", "d"], 3)).toEqual(["a", "b", "c"])
  })
})

describe("TagInput", () => {
  it("adds chips on Enter and comma and keeps the remaining draft", () => {
    render(<Harness />)
    fireEvent.change(input(), { target: { value: "netflix" } })
    fireEvent.keyDown(input(), { key: "Enter" })
    fireEvent.change(input(), { target: { value: "spotify, hbo" } })
    expect(chips()).toEqual(["netflix", "spotify"])
    expect(input().value).toBe("hbo")
  })

  it("only splits on Enter when comma is not a separator", () => {
    render(<Harness separators={["Enter"]} />)
    fireEvent.change(input(), { target: { value: "^a{1,3}$" } })
    expect(chips()).toEqual([])
    fireEvent.keyDown(input(), { key: "Enter" })
    expect(chips()).toEqual(["^a{1,3}$"])
    expect(input().value).toBe("")
  })

  it("removes the last chip with Backspace on an empty draft", () => {
    render(<Harness initial={["a", "b"]} />)
    fireEvent.keyDown(input(), { key: "Backspace" })
    expect(chips()).toEqual(["a"])
  })

  it("removes a chip with its button", () => {
    render(<Harness initial={["a", "b"]} />)
    fireEvent.click(screen.getByRole("button", { name: "Remove a" }))
    expect(chips()).toEqual(["b"])
  })

  it("splits pasted lists and dedupes them", () => {
    render(<Harness initial={["Mercadona"]} />)
    fireEvent.paste(input(), {
      clipboardData: { getData: () => "mercadona\nLidl, Aldi" },
    })
    expect(chips()).toEqual(["Mercadona", "Lidl", "Aldi"])
  })

  it("commits the draft on blur", () => {
    render(<Harness />)
    fireEvent.change(input(), { target: { value: "amazon" } })
    fireEvent.blur(input())
    expect(chips()).toEqual(["amazon"])
    expect(input().value).toBe("")
  })

  it("becomes read only once the maximum is reached", () => {
    render(<Harness initial={["a"]} maxItems={2} />)
    expect(input()).not.toHaveAttribute("readonly")
    fireEvent.change(input(), { target: { value: "b,c" } })
    expect(chips()).toEqual(["a", "b"])
    expect(input().value).toBe("")
    expect(input()).toHaveAttribute("readonly")
  })
})
