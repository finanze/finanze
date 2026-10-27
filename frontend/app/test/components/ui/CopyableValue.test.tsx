import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { CopyableValue } from "@/components/ui/CopyableValue"
import en from "@/i18n/locales/en.json"

const { copyToClipboard } = vi.hoisted(() => ({ copyToClipboard: vi.fn() }))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/lib/clipboard", () => ({ copyToClipboard }))

const ISIN = "US0378331005"

describe("CopyableValue", () => {
  beforeEach(() => {
    copyToClipboard.mockResolvedValue(true)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("copies the value on click and shows the copied state", async () => {
    const user = userEvent.setup()
    render(<CopyableValue value={ISIN} />)

    const button = screen.getByRole("button", { name: ISIN })
    expect(button).toHaveAttribute("title", en.common.copy)

    await user.click(button)

    expect(copyToClipboard).toHaveBeenCalledWith(ISIN)
    await waitFor(() =>
      expect(button).toHaveAttribute("title", en.common.copied),
    )
  })

  it("keeps the copy label when the clipboard fails", async () => {
    copyToClipboard.mockResolvedValue(false)
    const user = userEvent.setup()
    render(<CopyableValue value={ISIN} />)

    const button = screen.getByRole("button", { name: ISIN })
    await user.click(button)

    await waitFor(() => expect(copyToClipboard).toHaveBeenCalledWith(ISIN))
    expect(button).toHaveAttribute("title", en.common.copy)
  })

  it("restores the copy label after the feedback delay", async () => {
    const user = userEvent.setup()
    render(<CopyableValue value={ISIN} />)

    const button = screen.getByRole("button", { name: ISIN })
    await user.click(button)
    await waitFor(() =>
      expect(button).toHaveAttribute("title", en.common.copied),
    )

    await waitFor(
      () => expect(button).toHaveAttribute("title", en.common.copy),
      { timeout: 2500 },
    )
  })
})
