import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { prepareLightHaptic, triggerLightHaptic } from "@/lib/capacitor/haptics"

const haptics = vi.hoisted(() => ({
  isIOS: vi.fn(() => true),
  prepare: vi.fn().mockResolvedValue(undefined),
  impact: vi.fn().mockResolvedValue(undefined),
}))

vi.mock("@/lib/platform", () => ({ isIOS: haptics.isIOS }))
vi.mock("@/lib/capacitor/plugins", () => ({
  LightHaptics: { prepare: haptics.prepare, impact: haptics.impact },
}))

beforeEach(() => {
  vi.clearAllMocks()
  haptics.isIOS.mockReturnValue(true)
  haptics.prepare.mockReset().mockResolvedValue(undefined)
  haptics.impact.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe("prepared light haptics", () => {
  it("prepares silently and triggers feedback only on demand", () => {
    prepareLightHaptic()
    prepareLightHaptic()

    expect(haptics.prepare).toHaveBeenCalledTimes(2)
    expect(haptics.impact).not.toHaveBeenCalled()

    triggerLightHaptic()

    expect(haptics.impact).toHaveBeenCalledExactlyOnceWith()
  })

  it("does not prepare or trigger feedback outside iOS", () => {
    haptics.isIOS.mockReturnValue(false)

    prepareLightHaptic()
    triggerLightHaptic()

    expect(haptics.prepare).not.toHaveBeenCalled()
    expect(haptics.impact).not.toHaveBeenCalled()
  })

  it("handles preparation failures without preventing later feedback", async () => {
    const failure = new Error("Preparation unavailable")
    const logError = vi.spyOn(console, "error").mockImplementation(() => {})
    haptics.prepare.mockRejectedValueOnce(failure)

    prepareLightHaptic()
    await Promise.resolve()

    expect(logError).toHaveBeenCalledWith(
      "Failed to prepare haptic feedback:",
      failure,
    )
    expect(haptics.impact).not.toHaveBeenCalled()

    prepareLightHaptic()
    triggerLightHaptic()

    expect(haptics.prepare).toHaveBeenCalledTimes(2)
    expect(haptics.impact).toHaveBeenCalledExactlyOnceWith()
  })

  it("handles feedback failures without an unhandled rejection", async () => {
    const failure = new Error("Feedback unavailable")
    const logError = vi.spyOn(console, "error").mockImplementation(() => {})
    haptics.impact.mockRejectedValueOnce(failure)

    triggerLightHaptic()
    await Promise.resolve()

    expect(logError).toHaveBeenCalledWith(
      "Failed to trigger haptic feedback:",
      failure,
    )
  })
})
